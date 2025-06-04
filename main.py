from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import uuid
import time
import io
import os
import logging
from datetime import datetime, timedelta
import threading
from enum import Enum

# Import our optimized scraper
from scraper import OptimizedSBTETScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="SBTET Results API",
    description="API for fetching SBTET exam results and generating Excel reports",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://mydiplomaclassresults.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enums
class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ScrapeRequest(BaseModel):
    year: str = "22"
    college_code: str = "008"
    branch_code: str = "CM"
    start_pin: int = 1
    end_pin: int = 67
    semester: str = "5"

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str

class StatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress_percentage: float
    processed_count: int
    total_count: int
    success_count: int
    failed_count: int
    estimated_time_remaining: Optional[int] = None
    message: str
    created_at: datetime
    updated_at: datetime

# Global job storage (in production, use Redis or database)
jobs: Dict[str, Dict[str, Any]] = {}
job_scrapers: Dict[str, OptimizedSBTETScraper] = {}
job_lock = threading.Lock()

# Cleanup old jobs (older than 1 hour)
def cleanup_old_jobs():
    """Remove jobs older than 1 hour to prevent memory buildup."""
    current_time = datetime.now()
    with job_lock:
        jobs_to_remove = []
        for job_id, job_data in jobs.items():
            if current_time - job_data['created_at'] > timedelta(hours=1):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            jobs.pop(job_id, None)
            job_scrapers.pop(job_id, None)
            logger.info(f"Cleaned up old job: {job_id}")

def run_scraping_job(job_id: str, request: ScrapeRequest):
    """Background task to run the scraping job."""
    try:
        with job_lock:
            jobs[job_id]['status'] = JobStatus.IN_PROGRESS
            jobs[job_id]['updated_at'] = datetime.now()
            jobs[job_id]['message'] = "Starting scraping process..."

        # Create scraper instance
        scraper = OptimizedSBTETScraper()
        job_scrapers[job_id] = scraper
        
        logger.info(f"Starting scraping job {job_id}")
        
        # Update job with total count
        pin_count = request.end_pin - request.start_pin
        with job_lock:
            jobs[job_id]['total_count'] = pin_count
            jobs[job_id]['message'] = f"Processing {pin_count} students..."
        
        # Start scraping
        excel_buffer = scraper.scrape_results(
            year=request.year,
            branch_code=request.branch_code,
            college_code=request.college_code,
            pin_range=(request.start_pin, request.end_pin),
            semester=request.semester
        )
        
        # Job completed successfully
        with job_lock:
            jobs[job_id].update({
                'status': JobStatus.COMPLETED,
                'excel_data': excel_buffer,
                'updated_at': datetime.now(),
                'message': "Scraping completed successfully!",
                'processed_count': pin_count,
                'progress_percentage': 100.0
            })
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        with job_lock:
            jobs[job_id].update({
                'status': JobStatus.FAILED,
                'updated_at': datetime.now(),
                'message': f"Scraping failed: {str(e)}"
            })
    finally:
        # Cleanup scraper instance
        job_scrapers.pop(job_id, None)

# @app.get("/")
# async def root():
#     """Health check endpoint."""
#     return {
#         "message": "SBTET Results API is running",
#         "version": "1.0.0",
#         "status": "healthy",
#         "active_jobs": len(jobs)
#     }
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the frontend page."""
    html_file = Path("templates/index.html")
    return html_file.read_text()

@app.post("/api/start-scraping", response_model=JobResponse)
async def start_scraping(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Start a new scraping job."""
    MAX_CONCURRENT_JOBS = 3  
    try:
        # Validate input
        if request.start_pin >= request.end_pin:
            raise HTTPException(status_code=400, detail="start_pin must be less than end_pin")
        
        if request.end_pin - request.start_pin > 200:
            raise HTTPException(status_code=400, detail="Maximum 200 students per request")
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job
        with job_lock:
            jobs[job_id] = {
                'status': JobStatus.PENDING,
                'progress_percentage': 0.0,
                'processed_count': 0,
                'total_count': 0,
                'success_count': 0,
                'failed_count': 0,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'message': "Job created, waiting to start...",
                'request': request.dict(),
                'excel_data': None
            }
        
        # Start background task
        background_tasks.add_task(run_scraping_job, job_id, request)
        
        # Cleanup old jobs
        background_tasks.add_task(cleanup_old_jobs)
        active_jobs_count = sum(1 for job in jobs.values() 
            if job['status'] in [JobStatus.PENDING, JobStatus.IN_PROGRESS])

        if active_jobs_count >= MAX_CONCURRENT_JOBS:
            raise HTTPException(status_code=429, detail="Too many active jobs")
        
        return JobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            message="Scraping job started successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start scraping job: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start scraping job")

@app.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_job_status(job_id: str):
    """Get the status of a scraping job."""
    with job_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_data = jobs[job_id].copy()
    
    # Get real-time progress if job is in progress
    if job_data['status'] == JobStatus.IN_PROGRESS and job_id in job_scrapers:
        scraper = job_scrapers[job_id]
        current_progress = scraper.get_progress()
        
        # Update progress
        with job_lock:
            jobs[job_id]['progress_percentage'] = current_progress
            jobs[job_id]['processed_count'] = int(current_progress * job_data['total_count'] / 100)
            job_data = jobs[job_id].copy()
    
    # Calculate estimated time remaining
    estimated_time = None
    if job_data['status'] == JobStatus.IN_PROGRESS and job_data['progress_percentage'] > 0:
        elapsed_time = (datetime.now() - job_data['created_at']).total_seconds()
        remaining_progress = 100 - job_data['progress_percentage']
        if remaining_progress > 0:
            estimated_time = int((elapsed_time / job_data['progress_percentage']) * remaining_progress)
    
    return StatusResponse(
        job_id=job_id,
        status=job_data['status'],
        progress_percentage=job_data['progress_percentage'],
        processed_count=job_data['processed_count'],
        total_count=job_data['total_count'],
        success_count=job_data['success_count'],
        failed_count=job_data['failed_count'],
        estimated_time_remaining=estimated_time,
        message=job_data['message'],
        created_at=job_data['created_at'],
        updated_at=job_data['updated_at']
    )

@app.get("/api/download/{job_id}")
async def download_results(job_id: str):
    """Download the Excel file for a completed job."""
    with job_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_data = jobs[job_id]
        
        if job_data['status'] != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=400, 
                detail=f"Job is not completed. Current status: {job_data['status']}"
            )
        
        if job_data['excel_data'] is None:
            raise HTTPException(status_code=500, detail="Excel data not available")
        
        excel_data = job_data['excel_data']
    
    # Create filename
    request_data = job_data['request']
    filename = f"SBTET_Results_{request_data['year']}{request_data['college_code']}_{request_data['branch_code']}_Sem{request_data['semester']}.xlsx"
    
    # Prepare file for streaming
    excel_data.seek(0)
    file_stream = io.BytesIO(excel_data.read())
    file_stream.seek(0)
    
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/api/jobs")
async def list_jobs():
    """List all active jobs (for debugging)."""
    with job_lock:
        job_list = []
        for job_id, job_data in jobs.items():
            job_list.append({
                'job_id': job_id,
                'status': job_data['status'],
                'progress_percentage': job_data['progress_percentage'],
                'created_at': job_data['created_at'],
                'message': job_data['message']
            })
    
    return {
        'active_jobs': len(job_list),
        'jobs': job_list
    }

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a job (if it's not completed)."""
    with job_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_data = jobs[job_id]
        
        if job_data['status'] == JobStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Cannot cancel completed job")
        
        # Mark as failed/cancelled
        jobs[job_id].update({
            'status': JobStatus.FAILED,
            'message': "Job cancelled by user",
            'updated_at': datetime.now()
        })
    
    # Remove scraper instance
    job_scrapers.pop(job_id, None)
    
    return {"message": "Job cancelled successfully"}

# Add a simple endpoint for testing parameters
@app.get("/api/test-connection")
async def test_connection():
    """Enhanced test connection with detailed diagnostics."""
    try:
        scraper = OptimizedSBTETScraper()
        
        # First run diagnostics
        diagnosis = scraper.diagnose_connection_issue()
        
        # Try to analyze form
        form_data = scraper.analyze_form_structure()
        
        if form_data:
            return {
                "status": "success",
                "message": f"Successfully connected to SBTET website via {scraper.working_url}",
                "form_fields": len(form_data.get('hidden_fields', {})),
                "diagnostics": diagnosis,
                "working_url": scraper.working_url
            }
        else:
            return {
                "status": "error",
                "message": "Failed to analyze SBTET website form",
                "diagnostics": diagnosis,
                "suggestions": [
                    "Check if SBTET website is accessible from your location",
                    "Verify network connectivity in production environment",
                    "Check firewall settings for outbound connections"
                ]
            }
    except Exception as e:
        scraper = OptimizedSBTETScraper()
        diagnosis = scraper.diagnose_connection_issue()
        
        return {
            "status": "error",
            "message": f"Connection test failed: {str(e)}",
            "diagnostics": diagnosis,
            "suggestions": [
                "Check network connectivity in production environment",
                "Verify firewall allows outbound HTTPS connections",
                "Check if proxy configuration is needed",
                "Try again later - target server might be temporarily down"
            ]
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
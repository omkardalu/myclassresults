const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'  // Development
    : window.location.origin; 
let currentJobId = null;
let statusInterval = null;

// Check API connection on load
async function checkConnection() {
  const statusElement = document.getElementById('connectionStatus');
  try {
      const response = await fetch(`${API_BASE}/api/test-connection`);
      const data = await response.json();
      
      if (data.status === 'success') {
          statusElement.innerHTML = '✅ Connected to API';
          statusElement.className = 'connection-status connection-online';
      } else {
          statusElement.innerHTML = '⚠️ API Connection Issues';
          statusElement.className = 'connection-status connection-offline';
      }
  } catch (error) {
      statusElement.innerHTML = '❌ API Offline';
      statusElement.className = 'connection-status connection-offline';
  }

  setTimeout(() => {
      statusElement.style.display = 'none';
  }, 3000);
}

// Show alert message
function showAlert(message, type = 'info') {
  const container = document.getElementById('alertContainer');
  const alert = document.createElement('div');
  alert.className = `alert alert-${type}`;
  alert.innerHTML = message;
  container.appendChild(alert);

  setTimeout(() => {
      alert.remove();
  }, 5000);
}

// Handle form submission
document.getElementById('scrapingForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const formData = new FormData(e.target);
  const data = Object.fromEntries(formData.entries());
  
  // Convert numeric fields
  data.start_pin = parseInt(data.start_pin);
  data.end_pin = parseInt(data.end_pin);

  // Validation
  if (data.start_pin >= data.end_pin) {
      showAlert('Start PIN must be less than End PIN', 'error');
      return;
  }

  if (data.end_pin - data.start_pin > 200) {
      showAlert('Maximum 200 students per request', 'error');
      return;
  }

  const startBtn = document.getElementById('startBtn');
  const spinner = document.getElementById('loadingSpinner');
  
  startBtn.disabled = true;
  spinner.style.display = 'inline-block';

  try {
      const response = await fetch(`${API_BASE}/api/start-scraping`, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(data)
      });

      const result = await response.json();

      if (response.ok) {
          currentJobId = result.job_id;
          document.getElementById('jobId').textContent = result.job_id;
          document.getElementById('statusCard').classList.add('active');
          showAlert('Scraping job started successfully!', 'success');
          
          // Start monitoring
          startStatusMonitoring();
      } else {
          showAlert(result.detail || 'Failed to start scraping job', 'error');
      }
  } catch (error) {
      showAlert('Network error: Unable to connect to API', 'error');
  } finally {
      startBtn.disabled = false;
      spinner.style.display = 'none';
  }
});

// Start status monitoring
function startStatusMonitoring() {
  if (statusInterval) {
      clearInterval(statusInterval);
  }

  statusInterval = setInterval(async () => {
      if (currentJobId) {
          await updateJobStatus(currentJobId);
      }
  }, 2000); // Update every 2 seconds
}

// Update job status
async function updateJobStatus(jobId) {
  try {
      const response = await fetch(`${API_BASE}/api/status/${jobId}`);
      const status = await response.json();

      if (response.ok) {
          updateStatusDisplay(status);
          
          if (status.status === 'completed' || status.status === 'failed') {
              clearInterval(statusInterval);
              statusInterval = null;
          }
      } else {
          showAlert('Failed to fetch job status', 'error');
      }
  } catch (error) {
      console.error('Status update error:', error);
  }
}

// Update status display
function updateStatusDisplay(status) {
  document.getElementById('progressFill').style.width = `${status.progress_percentage}%`;
  document.getElementById('progressText').textContent = `${Math.round(status.progress_percentage)}%`;
  
  document.getElementById('processedCount').textContent = status.processed_count;
  document.getElementById('totalCount').textContent = status.total_count;
  document.getElementById('successCount').textContent = status.success_count;
  document.getElementById('failedCount').textContent = status.failed_count;
  
  const messageElement = document.getElementById('statusMessage');
  messageElement.textContent = status.message;
  messageElement.className = `alert alert-${getAlertType(status.status)}`;

  // Show estimated time
  const timeElement = document.getElementById('estimatedTime');
  if (status.estimated_time_remaining) {
      const minutes = Math.floor(status.estimated_time_remaining / 60);
      const seconds = status.estimated_time_remaining % 60;
      timeElement.textContent = `⏱️ Estimated time remaining: ${minutes}m ${seconds}s`;
  } else {
      timeElement.textContent = '';
  }

  // Show download button if completed
  const downloadSection = document.getElementById('downloadSection');
  if (status.status === 'completed') {
      downloadSection.style.display = 'block';
      document.getElementById('downloadBtn').href = `${API_BASE}/api/download/${status.job_id}`;
  } else {
      downloadSection.style.display = 'none';
  }
}

// Get alert type based on status
function getAlertType(status) {
  switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'in_progress': return 'info';
      default: return 'info';
  }
}

// Load recent jobs
async function loadRecentJobs() {
  try {
      const response = await fetch(`${API_BASE}/api/jobs`);
      const data = await response.json();

      const container = document.getElementById('jobsContainer');
      
      if (data.jobs && data.jobs.length > 0) {
          container.innerHTML = data.jobs.map(job => `
              <div class="job-item">
                  <div class="job-info">
                      <strong>Job ID:</strong> ${job.job_id}<br>
                      <small>Created: ${new Date(job.created_at).toLocaleString()}</small><br>
                      <small>${job.message}</small>
                  </div>
                  <div>
                      <span class="job-status status-${job.status}">${job.status}</span>
                      <div style="margin-top: 5px; font-size: 0.9rem;">
                          ${Math.round(job.progress_percentage)}%
                      </div>
                  </div>
              </div>
          `).join('');
      } else {
          container.innerHTML = '<p style="text-align: center; color: #666;">No recent jobs</p>';
      }
  } catch (error) {
      console.error('Failed to load jobs:', error);
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  checkConnection();
  loadRecentJobs();
  
  // Refresh jobs list every 10 seconds
  setInterval(loadRecentJobs, 10000);
});

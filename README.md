# MyClassResults - SBTET Results Scraper

A FastAPI-based web application to efficiently scrape and analyze SBTET (State Board of Technical Education and Training) exam results.

## Features

- Bulk results fetching for multiple students
- Excel report generation with formatted results
- Progress tracking with real-time updates
- Concurrent request handling with rate limiting
- Error handling and retry mechanisms

## Tech Stack

- Python 3.8+
- FastAPI
- BeautifulSoup4
- Pandas
- OpenPyXL
- PyPDF2
- Requests

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/myclassresults.git
cd myclassresults
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
.\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Development Setup

1. Create necessary directories:
```bash
mkdir static templates static\js
```

2. Copy static files to appropriate directories:
- Place JavaScript files in `static/js/`
- Place HTML templates in `templates/`

3. Create environment variables file (.env):
```
DEBUG=True
HOST=localhost
PORT=8000
```

## Running the Application

1. Start the development server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. Access the application:
- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## API Endpoints

- `GET /` - Web interface
- `POST /api/start-scraping` - Start scraping job
- `GET /api/status/{job_id}` - Check job status
- `GET /api/download/{job_id}` - Download results Excel file
- `GET /api/test-connection` - Test SBTET website connectivity

## Project Structure

```
myclassresults/
├── static/
│   └── js/
│       └── scripts.js
├── templates/
│   └── index.html
├── main.py
├── scraper.py
├── requirements.txt
└── README.md
```

## Configuration

Key configuration variables in `scraper.py`:
- `MAX_CONCURRENT_REQUESTS`: Maximum concurrent requests (default: 2)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 15)
- `MAX_RETRIES`: Maximum retry attempts (default: 2)

## Deployment

The application is configured for deployment on Render. Key considerations:

1. Set environment variables in Render dashboard
2. Configure build command:
```bash
pip install -r requirements.txt
```

3. Configure start command:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - See LICENSE file for details

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.
# Bulk Certificate Generator

A small web application for creating personalized PDF certificates for event attendees. Enter recipients manually or upload a CSV, then download each certificate or a ZIP of the complete batch.

## Features

- Responsive, browser-based interface for event details and recipient entry
- Manual recipient entry and CSV upload
- Input validation with readable error messages
- Personalized PDF certificate generation
- SQLite persistence for jobs and certificates
- Individual PDF and batch ZIP downloads
- REST API with health check and OpenAPI docs

## Technology stack

- Python 3.10+
- FastAPI and Uvicorn
- SQLAlchemy 2 and SQLite
- ReportLab
- HTML, CSS, and vanilla JavaScript
- Pytest and FastAPI TestClient

## Architecture

The browser UI is served by FastAPI from `templates/` and `static/`. The API validates a manual or CSV recipient list, stores a certificate job and recipient metadata through SQLAlchemy, and uses ReportLab to write PDF files into `generated/`. Certificate records refer only to application-generated filenames. Downloads resolve those filenames inside the generated-files directory; ZIP files are assembled when requested and are not persisted.

## Folder structure

```text
bulk-certificate-generator/
├── app/
│   ├── __init__.py
│   ├── certificate_generator.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── generated/                 # Generated PDFs and ZIP files are ignored by Git
├── static/
│   ├── app.js
│   └── style.css
├── templates/
│   └── index.html
├── tests/
│   ├── conftest.py
│   ├── test_csv_and_downloads.py
│   ├── test_jobs.py
│   └── test_web.py
├── .gitignore
├── README.md
└── requirements.txt
```

## Installation

Python 3.10 or newer is recommended. From the project directory:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On macOS/Linux, activate with `source venv/bin/activate`.

## Start the server

```powershell
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>. The SQLite database is created as `certificates.db` in the project root on startup.

Optional environment settings:

- `DATABASE_URL`: SQLAlchemy database URL; defaults to the local SQLite database.
- `CORS_ORIGINS`: comma-separated browser origins allowed to call the API; defaults to `http://localhost:3000,http://localhost:5173`. The bundled UI is same-origin and does not require CORS.

## API endpoints

All validation failures return HTTP 400 with a `detail` message. Missing jobs or certificates return HTTP 404. Unexpected generation or file errors return a generic HTTP 500 message; details are logged by the server.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Serve the web interface |
| `GET` | `/health` | Check server health |
| `POST` | `/jobs` | Generate certificates from JSON recipients |
| `GET` | `/jobs/{job_id}` | Read a job and its certificate download links |
| `POST` | `/jobs/csv` | Generate certificates from an uploaded CSV |
| `GET` | `/certificates/{certificate_id}/download` | Download one PDF |
| `GET` | `/jobs/{job_id}/download` | Download a ZIP of the job's PDFs |

### Example JSON request

```json
{
  "event_name": "Annual Tech Symposium",
  "event_date": "2026-10-08",
  "recipients": [
    { "name": "Varsha R", "email": "varsha@example.com" },
    { "name": "Rahul Kumar", "email": "rahul@example.com" }
  ]
}
```

Example request:

```powershell
curl.exe -X POST http://127.0.0.1:8000/jobs `
  -H "Content-Type: application/json" `
  -d '{"event_name":"Annual Tech Symposium","event_date":"2026-10-08","recipients":[{"name":"Varsha R","email":"varsha@example.com"}]}'
```

The response includes a numeric `id` (the job ID), a certificate count, and a `download_url` for every generated certificate. Use `GET /jobs/{job_id}` to retrieve those details later, or `GET /jobs/{job_id}/download` to download all PDFs as a ZIP.

### CSV format

CSV files must be UTF-8 encoded, have a `.csv` extension, and contain exactly the `name` and `email` columns. Either column order is accepted; a UTF-8 BOM is supported. Blank lines are ignored. Each nonblank row needs a name and a valid email address. Files are limited to 5 MB and 500 recipients.

```csv
name,email
Varsha R,varsha@example.com
Rahul Kumar,rahul@example.com
```

Upload using multipart form fields `event_name`, `event_date` (`YYYY-MM-DD`), and `file`:

```powershell
curl.exe -X POST http://127.0.0.1:8000/jobs/csv `
  -F "event_name=Annual Tech Symposium" `
  -F "event_date=2026-10-08" `
  -F "file=@recipients.csv"
```

## Example project workflow

1. Start the server and open the web page.
2. Enter an event name and date.
3. Add each recipient manually or upload a CSV file.
4. Select **Generate certificates** and review the success message and job ID.
5. Download individual PDFs from the result list, or download the complete batch as a ZIP.
6. Use the job ID with `GET /jobs/{job_id}` to look up the batch later.

## Run tests

```powershell
python -m pytest -q
```

Tests use an isolated in-memory SQLite database and temporary generated PDFs; they do not modify the local project database.

## Git hygiene

The `.gitignore` excludes virtual environments, bytecode, `.env` files, the SQLite database, generated PDFs/ZIP files, editor settings, and test artifacts. Do not commit secrets or generated output.

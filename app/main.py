import csv
import io
import logging
import os
import re
import uuid
import zipfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Callable

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.staticfiles import StaticFiles

from app import models
from app.certificate_generator import generate_certificate
from app.database import SessionLocal, ensure_database_schema, engine
from app.models import Certificate, CertificateJob
from app.schemas import JobCreate, RecipientInput

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = PROJECT_ROOT / "generated"
MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_RECIPIENTS = 500
CSV_HEADERS = {"name", "email"}


def _job_payload(job: CertificateJob) -> dict:
    return {
        "id": job.id,
        "event_name": job.event_name,
        "event_date": job.event_date.isoformat(),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "certificate_count": len(job.certificates),
        "total": job.total_count,
        "successful": job.successful_count,
        "failed": job.failed_count,
        "status": job.status,
        "certificates": [
            {
                "id": certificate.id,
                "recipient_name": certificate.recipient_name,
                "recipient_email": certificate.recipient_email,
                "status": certificate.status,
                "error_message": certificate.error_message,
                "download_url": f"/certificates/{certificate.id}/download",
            }
            for certificate in job.certificates
        ],
    }


def _safe_certificate_path(filename: str) -> Path:
    if not re.fullmatch(r"certificate_[0-9a-f]{32}\.pdf", filename):
        raise HTTPException(status_code=404, detail="Certificate file not found.")
    base = GENERATED_DIR.resolve()
    path = (base / filename).resolve()
    if path.parent != base:
        raise HTTPException(status_code=404, detail="Certificate file not found.")
    if not path.is_file():
        logger.error("Generated certificate file is missing: %s", filename)
        raise HTTPException(status_code=500, detail="A generated certificate file is unavailable.")
    return path


def _parse_csv(data: bytes) -> list[RecipientInput]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must use UTF-8 encoding.") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=400, detail="CSV is empty. Include the headers: name,email."
        )

    headers = [header.strip().lower() if header else "" for header in reader.fieldnames]
    if len(headers) != len(set(headers)) or set(headers) != CSV_HEADERS:
        raise HTTPException(
            status_code=400,
            detail="CSV headers must be exactly name,email (either order is accepted).",
        )
    reader.fieldnames = headers

    recipients: list[RecipientInput] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise HTTPException(
                status_code=400,
                detail=f"CSV row {row_number} has more values than the header.",
            )
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            recipients.append(RecipientInput.model_validate(row))
        except ValidationError as exc:
            issue = exc.errors()[0]
            field = str(issue["loc"][0])
            reason = issue["msg"].removeprefix("Value error, ")
            raise HTTPException(
                status_code=400,
                detail=f"CSV row {row_number}: invalid {field}: {reason}",
            ) from exc
        if len(recipients) > MAX_RECIPIENTS:
            raise HTTPException(
                status_code=400,
                detail=f"CSV may contain at most {MAX_RECIPIENTS} recipients.",
            )

    if not recipients:
        raise HTTPException(status_code=400, detail="CSV contains no recipient rows.")
    return recipients


def _create_job(
    payload: JobCreate, db: Session
) -> CertificateJob:
    job = CertificateJob(
        event_name=payload.event_name,
        event_date=payload.event_date,
        status="PROCESSING",
        total_count=len(payload.recipients),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    for recipient in payload.recipients:
        filename = f"certificate_{uuid.uuid4().hex}.pdf"
        output_path = GENERATED_DIR / filename
        certificate = Certificate(
            job_id=job.id,
            recipient_name=recipient.name,
            recipient_email=recipient.email,
            filename=filename,
            status="PROCESSING",
        )
        db.add(certificate)
        db.commit()
        db.refresh(certificate)

        try:
            generate_certificate(
                recipient.name, payload.event_name, payload.event_date, output_path
            )
        except Exception:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Could not remove failed certificate file for certificate %s.",
                    certificate.id,
                )
            certificate.status = "FAILED"
            certificate.error_message = "Certificate PDF generation failed."
            job.failed_count += 1
            logger.exception("Certificate %s generation failed.", certificate.id)
        else:
            certificate.status = "COMPLETED"
            job.successful_count += 1

        db.commit()

    if job.failed_count == job.total_count:
        job.status = "FAILED"
    elif job.failed_count:
        job.status = "PARTIAL"
    else:
        job.status = "COMPLETED"
    db.commit()
    db.refresh(job)
    return job


def create_app(
    database_engine: Engine = engine,
    session_factory: Callable[[], Session] = SessionLocal,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        ensure_database_schema(database_engine)
        yield

    app = FastAPI(
        title="Bulk Certificate Generator",
        description="Generate and download personalized PDF certificates in bulk.",
        version="1.0.0",
        lifespan=lifespan,
    )
    cors_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.mount(
        "/static",
        StaticFiles(directory=str(PROJECT_ROOT / "static")),
        name="static",
    )

    def get_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        messages = []
        for error in exc.errors():
            location = ".".join(str(item) for item in error["loc"] if item != "body")
            message = error["msg"].removeprefix("Value error, ")
            messages.append(f"{location}: {message}" if location else message)
        return JSONResponse(status_code=400, content={"detail": "; ".join(messages)})

    @app.get("/", include_in_schema=False)
    async def home():
        return FileResponse(PROJECT_ROOT / "templates" / "index.html")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/jobs", status_code=201)
    async def create_job_endpoint(
        payload: JobCreate, db: Session = Depends(get_session)
    ):
        job = _create_job(payload, db)
        return _job_payload(job)

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: int, db: Session = Depends(get_session)):
        job = db.query(CertificateJob).filter(CertificateJob.id == job_id).first()
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return _job_payload(job)

    @app.post("/jobs/csv", status_code=201)
    async def create_job_from_csv(
        event_name: str = Form(..., min_length=1, max_length=200),
        event_date: date = Form(...),
        file: UploadFile = File(...),
        db: Session = Depends(get_session),
    ):
        event_name = event_name.strip()
        if not event_name:
            raise HTTPException(status_code=400, detail="Event name cannot be empty.")
        if Path(file.filename or "").suffix.lower() != ".csv":
            raise HTTPException(status_code=400, detail="Upload a .csv file.")
        data = await file.read(MAX_CSV_BYTES + 1)
        if len(data) > MAX_CSV_BYTES:
            raise HTTPException(status_code=400, detail="CSV file must be 5 MB or smaller.")
        recipients = _parse_csv(data)
        try:
            payload = JobCreate(
                event_name=event_name, event_date=event_date, recipients=recipients
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid event or recipient data."
            ) from exc
        return _job_payload(_create_job(payload, db))

    @app.get("/certificates/{certificate_id}/download")
    async def download_certificate(
        certificate_id: int, db: Session = Depends(get_session)
    ):
        certificate = (
            db.query(Certificate).filter(Certificate.id == certificate_id).first()
        )
        if certificate is None:
            raise HTTPException(status_code=404, detail="Certificate not found.")
        if certificate.status != "COMPLETED":
            raise HTTPException(
                status_code=404,
                detail="Certificate was not generated successfully.",
            )
        path = _safe_certificate_path(certificate.filename)
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=certificate.filename,
        )

    @app.get("/jobs/{job_id}/download")
    async def download_job_zip(job_id: int, db: Session = Depends(get_session)):
        job = db.query(CertificateJob).filter(CertificateJob.id == job_id).first()
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        completed_certificates = [
            certificate
            for certificate in job.certificates
            if certificate.status == "COMPLETED"
        ]
        if not completed_certificates:
            raise HTTPException(
                status_code=404,
                detail="This job has no successfully generated certificates.",
            )

        archive_buffer = io.BytesIO()
        try:
            with zipfile.ZipFile(
                archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for certificate in completed_certificates:
                    path = _safe_certificate_path(certificate.filename)
                    archive.write(path, arcname=certificate.filename)
        except HTTPException:
            raise
        except (OSError, zipfile.BadZipFile) as exc:
            logger.exception("Could not create ZIP for job %s.", job_id)
            raise HTTPException(
                status_code=500, detail="Could not prepare the certificate ZIP."
            ) from exc

        archive_buffer.seek(0)
        return StreamingResponse(
            archive_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="certificates-job-{job.id}.zip"'
            },
        )

    return app


app = create_app()

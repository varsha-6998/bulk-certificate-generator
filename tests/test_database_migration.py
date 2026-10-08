from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import ensure_database_schema
from app.models import Certificate, CertificateJob


def test_existing_database_is_upgraded_with_successful_certificate_statuses(tmp_path):
    database_engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with database_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE certificate_jobs (
                    id INTEGER PRIMARY KEY,
                    event_name VARCHAR(200) NOT NULL,
                    event_date DATE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE certificates (
                    id INTEGER PRIMARY KEY,
                    job_id INTEGER NOT NULL,
                    recipient_name VARCHAR(120) NOT NULL,
                    recipient_email VARCHAR(254) NOT NULL,
                    filename VARCHAR(80) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO certificate_jobs (id, event_name, event_date) "
                "VALUES (1, 'Legacy event', '2026-10-08')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO certificates "
                "(id, job_id, recipient_name, recipient_email, filename) "
                "VALUES (1, 1, 'Existing attendee', 'attendee@example.com', "
                "'certificate_0123456789abcdef0123456789abcdef.pdf')"
            )
        )

    ensure_database_schema(database_engine)

    session = sessionmaker(bind=database_engine)()
    job = session.query(CertificateJob).filter_by(id=1).one()
    certificate = session.query(Certificate).filter_by(id=1).one()
    assert job.status == "COMPLETED"
    assert job.total_count == 1
    assert job.successful_count == 1
    assert job.failed_count == 0
    assert certificate.status == "COMPLETED"
    assert certificate.error_message is None
    session.close()
    database_engine.dispose()

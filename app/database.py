import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_URL = f"sqlite:///{(PROJECT_ROOT / 'certificates.db').as_posix()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def ensure_database_schema(database_engine=engine) -> None:
    Base.metadata.create_all(bind=database_engine)

    inspector = inspect(database_engine)
    migrations = {
        "certificate_jobs": {
            "status": "VARCHAR(20) NOT NULL DEFAULT 'COMPLETED'",
            "total_count": "INTEGER NOT NULL DEFAULT 0",
            "successful_count": "INTEGER NOT NULL DEFAULT 0",
            "failed_count": "INTEGER NOT NULL DEFAULT 0",
        },
        "certificates": {
            "status": "VARCHAR(20) NOT NULL DEFAULT 'COMPLETED'",
            "error_message": "TEXT",
        },
    }
    missing_columns = {
        table_name: {
            column_name: definition
            for column_name, definition in columns.items()
            if column_name
            not in {column["name"] for column in inspector.get_columns(table_name)}
        }
        for table_name, columns in migrations.items()
    }

    if not any(missing_columns.values()):
        return

    with database_engine.begin() as connection:
        for table_name, columns in missing_columns.items():
            for column_name, definition in columns.items():
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                    )
                )

        if missing_columns["certificate_jobs"] or missing_columns["certificates"]:
            connection.execute(
                text(
                    """
                    UPDATE certificate_jobs
                    SET total_count = (
                            SELECT COUNT(*) FROM certificates
                            WHERE certificates.job_id = certificate_jobs.id
                        ),
                        successful_count = (
                            SELECT COUNT(*) FROM certificates
                            WHERE certificates.job_id = certificate_jobs.id
                              AND certificates.status = 'COMPLETED'
                        ),
                        failed_count = (
                            SELECT COUNT(*) FROM certificates
                            WHERE certificates.job_id = certificate_jobs.id
                              AND certificates.status = 'FAILED'
                        ),
                        status = CASE
                            WHEN NOT EXISTS (
                                SELECT 1 FROM certificates
                                WHERE certificates.job_id = certificate_jobs.id
                                  AND certificates.status != 'COMPLETED'
                            ) THEN 'COMPLETED'
                            WHEN NOT EXISTS (
                                SELECT 1 FROM certificates
                                WHERE certificates.job_id = certificate_jobs.id
                                  AND certificates.status = 'COMPLETED'
                            ) THEN 'FAILED'
                            ELSE 'PARTIAL'
                        END
                    """
                )
            )

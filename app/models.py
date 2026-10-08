from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CertificateJob(Base):
    __tablename__ = "certificate_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    certificates: Mapped[list["Certificate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("certificate_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(254), nullable=False)
    filename: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    job: Mapped[CertificateJob] = relationship(back_populates="certificates")

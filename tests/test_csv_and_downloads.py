import io
import zipfile


def test_csv_generation_individual_pdf_and_zip(client):
    response = client.post(
        "/jobs/csv",
        data={"event_name": "Community Day", "event_date": "2026-10-08"},
        files={
            "file": (
                "attendees.csv",
                b"name,email\r\nVarsha R,varsha@example.com\r\nRahul Kumar,rahul@example.com\r\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    job = response.json()
    assert job["certificate_count"] == 2
    assert job["status"] == "COMPLETED"
    assert job["successful"] == 2

    certificate_response = client.get(job["certificates"][0]["download_url"])
    assert certificate_response.status_code == 200
    assert certificate_response.headers["content-type"] == "application/pdf"
    assert certificate_response.content.startswith(b"%PDF")

    zip_response = client.get(f"/jobs/{job['id']}/download")
    assert zip_response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
        assert len(archive.namelist()) == 2
        assert all(name.endswith(".pdf") for name in archive.namelist())
        assert all(archive.read(name).startswith(b"%PDF") for name in archive.namelist())


def test_partial_job_zip_contains_only_successful_certificates(client, monkeypatch):
    from app import main

    def fail_second_certificate(name, event_name, event_date, output_path):
        if name == "Rahul Kumar":
            output_path.write_bytes(b"partial")
            raise OSError("simulated PDF failure")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(f"PDF for {name}".encode())

    monkeypatch.setattr(main, "generate_certificate", fail_second_certificate)
    response = client.post(
        "/jobs",
        json={
            "event_name": "Community Day",
            "event_date": "2026-10-08",
            "recipients": [
                {"name": "Varsha R", "email": "varsha@example.com"},
                {"name": "Rahul Kumar", "email": "rahul@example.com"},
                {"name": "Asha Patel", "email": "asha@example.com"},
            ],
        },
    )
    job = response.json()
    zip_response = client.get(f"/jobs/{job['id']}/download")
    assert zip_response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
        assert len(archive.namelist()) == 2
        assert all(archive.read(name).startswith(b"PDF for") for name in archive.namelist())
    failed = client.get(job["certificates"][1]["download_url"])
    assert failed.status_code == 404


def test_invalid_csv_has_readable_error(client):
    response = client.post(
        "/jobs/csv",
        data={"event_name": "Workshop", "event_date": "2026-10-08"},
        files={"file": ("recipients.csv", b"full_name,email\nAda,ada@example.com\n", "text/csv")},
    )
    assert response.status_code == 400
    assert "headers must be exactly name,email" in response.json()["detail"]


def test_downloads_for_missing_records_return_404(client):
    assert client.get("/certificates/123456/download").status_code == 404
    assert client.get("/jobs/123456/download").status_code == 404

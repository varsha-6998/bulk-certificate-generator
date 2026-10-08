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

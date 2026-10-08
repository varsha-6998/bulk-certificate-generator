from datetime import date


def test_one_certificate_failure_does_not_stop_job(client, monkeypatch, tmp_path):
    from app import main

    generated_dir = tmp_path / "generated"
    calls = []

    def fail_second_certificate(name, event_name, event_date, output_path):
        calls.append(name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"partial pdf")
        if name == "Rahul Kumar":
            raise OSError("simulated PDF failure")
        output_path.write_bytes(f"PDF for {name}".encode())

    monkeypatch.setattr(main, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(main, "generate_certificate", fail_second_certificate)

    response = client.post(
        "/jobs",
        json={
            "event_name": "Tech Symposium",
            "event_date": "2026-10-08",
            "recipients": [
                {"name": "Varsha R", "email": "varsha@example.com"},
                {"name": "Rahul Kumar", "email": "rahul@example.com"},
                {"name": "Asha Patel", "email": "asha@example.com"},
            ],
        },
    )

    assert response.status_code == 201
    job = response.json()
    assert calls == ["Varsha R", "Rahul Kumar", "Asha Patel"]
    assert job["status"] == "PARTIAL"
    assert job["total"] == 3
    assert job["successful"] == 2
    assert job["failed"] == 1
    assert [certificate["status"] for certificate in job["certificates"]] == [
        "COMPLETED",
        "FAILED",
        "COMPLETED",
    ]
    assert job["certificates"][1]["error_message"]

    assert len(list(generated_dir.glob("*.pdf"))) == 2
    for certificate in (job["certificates"][0], job["certificates"][2]):
        download = client.get(certificate["download_url"])
        assert download.status_code == 200
        assert download.content.startswith(b"PDF for")
    assert client.get(job["certificates"][1]["download_url"]).status_code == 404

    readback = client.get(f"/jobs/{job['id']}")
    assert readback.status_code == 200
    assert readback.json()["status"] == "PARTIAL"
    assert [item["status"] for item in readback.json()["certificates"]] == [
        "COMPLETED",
        "FAILED",
        "COMPLETED",
    ]
    assert readback.json()["certificates"][1]["error_message"]


def test_job_status_when_all_certificates_fail(client, monkeypatch):
    from app import main

    monkeypatch.setattr(
        main,
        "generate_certificate",
        lambda *args: (_ for _ in ()).throw(OSError("simulated PDF failure")),
    )
    response = client.post(
        "/jobs",
        json={
            "event_name": "Tech Symposium",
            "event_date": "2026-10-08",
            "recipients": [
                {"name": "Varsha R", "email": "varsha@example.com"},
                {"name": "Rahul Kumar", "email": "rahul@example.com"},
            ],
        },
    )

    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "FAILED"
    assert job["total"] == 2
    assert job["successful"] == 0
    assert job["failed"] == 2
    assert all(item["status"] == "FAILED" for item in job["certificates"])
    assert client.get(f"/jobs/{job['id']}/download").status_code == 404


def test_create_and_read_job(client):
    response = client.post(
        "/jobs",
        json={
            "event_name": "Tech Symposium",
            "event_date": "2026-10-08",
            "recipients": [
                {"name": "Varsha R", "email": "varsha@example.com"},
                {"name": "Rahul Kumar", "email": "rahul@example.com"},
            ],
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["certificate_count"] == 2
    assert created["status"] == "COMPLETED"
    assert created["total"] == 2
    assert created["successful"] == 2
    assert created["failed"] == 0
    assert created["event_date"] == date(2026, 10, 8).isoformat()
    assert all(item["download_url"].startswith("/certificates/") for item in created["certificates"])

    read_response = client.get(f"/jobs/{created['id']}")
    assert read_response.status_code == 200
    assert read_response.json()["id"] == created["id"]
    assert len(read_response.json()["certificates"]) == 2


def test_invalid_job_input_returns_clear_400(client):
    response = client.post(
        "/jobs",
        json={
            "event_name": "",
            "event_date": "not-a-date",
            "recipients": [{"name": "", "email": "not-an-email"}],
        },
    )
    assert response.status_code == 400
    assert "event_name" in response.json()["detail"]


def test_missing_job_returns_404(client):
    response = client.get("/jobs/987654")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."

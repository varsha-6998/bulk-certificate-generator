from datetime import date


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

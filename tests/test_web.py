def test_home_page_and_health_endpoint(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "Certificates, made in bulk." in home.text
    assert "/static/app.js" in home.text

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "Generate certificates" in script.text

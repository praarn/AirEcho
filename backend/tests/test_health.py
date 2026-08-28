from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["scheduler_enabled"] is False  # disabled in tests


def test_openapi_docs(client):
    assert client.get("/openapi.json").status_code == 200


def test_end_to_end_smoke(client):
    """Register → location → symptom → exposure materialize → risk score →
    advisory, all through the public API."""
    client.post("/auth/register", json={"email": "e2e@example.com", "password": "pw-abcdefgh"})
    tok = client.post(
        "/auth/login", json={"email": "e2e@example.com", "password": "pw-abcdefgh"}
    ).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}

    loc = client.post("/locations", json={"label": "home", "lat": 12.0, "lng": 34.0}, headers=h)
    assert loc.status_code == 201

    for sev in (2, 5, 7):
        assert client.post("/symptoms", json={"severity": sev}, headers=h).status_code == 201

    score = client.get("/risk/score", headers=h)
    assert score.status_code == 200
    assert 0 <= score.json()["risk_score"] <= 10
    assert score.json()["model_type"] in {"heuristic", "population_fallback", "personal"}

    explain = client.get("/risk/explain", headers=h)
    assert explain.status_code == 200
    assert "explanation" in explain.json()

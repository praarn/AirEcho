from __future__ import annotations


def test_register_login_me(client):
    r = client.post("/auth/register", json={"email": "x@example.com", "password": "pw-abcdefgh"})
    assert r.status_code == 201

    r = client.post("/auth/login", json={"email": "x@example.com", "password": "pw-abcdefgh"})
    assert r.status_code == 200
    tok = r.json()
    assert tok["access_token"] and tok["refresh_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "x@example.com"


def test_duplicate_email_rejected(client):
    client.post("/auth/register", json={"email": "d@example.com", "password": "pw-abcdefgh"})
    r = client.post("/auth/register", json={"email": "d@example.com", "password": "pw-abcdefgh"})
    assert r.status_code == 409


def test_bad_password_rejected(client):
    client.post("/auth/register", json={"email": "b@example.com", "password": "pw-abcdefgh"})
    r = client.post("/auth/login", json={"email": "b@example.com", "password": "wrong-one"})
    assert r.status_code == 401


def test_refresh_rotates_and_old_token_is_dead(client):
    client.post("/auth/register", json={"email": "r@example.com", "password": "pw-abcdefgh"})
    first = client.post(
        "/auth/login", json={"email": "r@example.com", "password": "pw-abcdefgh"}
    ).json()

    second = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    new_refresh = second.json()["refresh_token"]
    assert new_refresh != first["refresh_token"]

    # the original refresh token no longer works
    replay = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401


def test_refresh_reuse_revokes_the_whole_chain(client):
    client.post("/auth/register", json={"email": "c@example.com", "password": "pw-abcdefgh"})
    t0 = client.post(
        "/auth/login", json={"email": "c@example.com", "password": "pw-abcdefgh"}
    ).json()
    t1 = client.post("/auth/refresh", json={"refresh_token": t0["refresh_token"]}).json()

    # attacker replays the already-rotated t0 → reuse detected
    bad = client.post("/auth/refresh", json={"refresh_token": t0["refresh_token"]})
    assert bad.status_code == 401
    assert "reuse" in bad.json()["detail"]

    # and the legitimately-rotated t1 is now also dead
    after = client.post("/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert after.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/risk/score").status_code == 401

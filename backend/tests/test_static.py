def test_api_404_stays_json(client):
    res = client.get("/api/definitely-not-a-route")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/json")

from app.main import _resolve_within


def test_api_404_stays_json(client):
    res = client.get("/api/definitely-not-a-route")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/json")


def test_resolve_within_blocks_path_traversal(tmp_path):
    # Build a fake frontend/dist: <tmp>/dist/index.html plus a secret file
    # outside of it at <tmp>/secret.txt, mirroring the real deployment shape
    # where FRONTEND_DIST is a subdirectory and other files live above it.
    base = tmp_path / "dist"
    base.mkdir()
    index_html = base / "index.html"
    index_html.write_text("<div id='root'></div>")
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")

    traversal_attempts = [
        "../secret.txt",
        "../../secret.txt",
        "assets/../../secret.txt",
        "a/b/../../../secret.txt",
    ]
    for full_path in traversal_attempts:
        result = _resolve_within(base, full_path)
        assert result == index_html.resolve(), f"traversal not blocked for {full_path!r}"
        assert result != secret.resolve()

    # Sanity checks so the test can't pass merely by always returning
    # index.html regardless of input: a real file inside base is served,
    # and a missing-but-safe path still falls back to index.html.
    (base / "vite.svg").write_text("<svg></svg>")
    assert _resolve_within(base, "vite.svg") == (base / "vite.svg").resolve()
    assert _resolve_within(base, "some/unknown/route") == index_html.resolve()

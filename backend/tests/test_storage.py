from app import storage


def test_not_configured_by_default():
    assert storage.is_r2_configured() is False


def test_validate_file_rules():
    assert storage.validate_file("apuntes.pdf", 1000) is None
    assert storage.validate_file("foto.JPG", 1000) is None
    assert "tipo" in storage.validate_file("virus.exe", 1000).lower()
    assert "grande" in storage.validate_file("big.pdf", storage.MAX_FILE_SIZE + 1).lower()
    assert storage.validate_file("noext", 1000) is not None


def test_config_reports_uploads_disabled(client):
    body = client.get("/api/config").json()
    assert body["file_uploads_enabled"] is False

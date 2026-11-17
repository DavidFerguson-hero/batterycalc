"""GET /health: up, and which optional features are switched on (read by the uptime check)."""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_reports_features_switched_on(monkeypatch):
    monkeypatch.setenv("EPC_API_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert client.get("/health").json() == {"status": "ok", "features": {"epc_lookup": True, "ai_summary": True}}


def test_health_reports_missing_keys_without_revealing_them(monkeypatch):
    monkeypatch.delenv("EPC_API_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-value")
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["features"] == {"epc_lookup": False, "ai_summary": True}
    assert "secret-value" not in str(body)

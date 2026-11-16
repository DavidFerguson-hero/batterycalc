"""POST /api/v2/summary — the AI-written summary (task 2.9). The Claude call is faked."""
from types import SimpleNamespace

import anthropic
import pytest
from fastapi.testclient import TestClient

from main import app
from models.assess import AssessResponse
from routers import summary as mod

client = TestClient(app)


@pytest.fixture(scope="module")
def assessed() -> dict:
    r = client.post("/api/v2/assess", json={
        "usage": {"route": "estimate", "annual_kwh": 3500, "property_type": "semi"},
        "tariff": {"current_tariff_key": "octopusGo"},
    })
    assert r.status_code == 200
    return r.json()


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    mod._hits.clear()
    yield
    mod._hits.clear()


def fake_reply(text: str, stop: str = "end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="thinking", thinking=""),
                                                       SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return self.reply


def use(monkeypatch, fake):
    monkeypatch.setattr(mod, "_get_client", lambda: fake)
    return fake


# ── Facts ─────────────────────────────────────────────────────────────────────

def test_facts_hold_the_headline_figures_and_no_half_hourly_data(assessed):
    a = AssessResponse.model_validate(assessed)
    facts = mod.build_facts(a)
    assert mod._gbp(a.recommendation.installed_price) in facts
    assert mod._gbp(a.headline.year1_battery_saving) in facts
    assert a.recommendation.tariff_name in facts
    assert "estimate" in facts
    # Only the summary figures: the facts stay short and carry no profile arrays.
    assert len(facts) < 2000 and "[" not in facts


def test_pound_figures_and_the_made_up_number_check():
    facts = "Costs £6,500. Saves £707 a year. Ahead −£2,300."
    assert mod.pound_figures(facts) == {6500, 707, 2300}
    assert mod.only_known_figures("It costs about £6,500 and saves £707.", facts)
    assert mod.only_known_figures("No pounds mentioned at all.", facts)
    assert not mod.only_known_figures("You'd save £88 by switching.", facts)


# ── Endpoint ──────────────────────────────────────────────────────────────────

def test_summary_uses_haiku_low_effort_and_returns_the_text(monkeypatch, assessed):
    a = AssessResponse.model_validate(assessed)
    price = mod._gbp(a.recommendation.installed_price)
    fake = use(monkeypatch, FakeClient(fake_reply(f"Not yet. A battery costs about {price} fitted.")))
    r = client.post("/api/v2/summary", json=assessed)
    assert r.status_code == 200, r.text
    assert r.json() == {"summary": f"Not yet. A battery costs about {price} fitted.", "model": "claude-haiku-5-5"}
    call = fake.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_config"] == {"effort": "low"}
    assert "temperature" not in call and "thinking" not in call
    assert "Facts:" in call["messages"][0]["content"]


def test_a_reply_with_an_invented_figure_is_not_shown(monkeypatch, assessed):
    use(monkeypatch, FakeClient(fake_reply("You'd save £123,457 a year.")))
    assert client.post("/api/v2/summary", json=assessed).status_code == 502


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_refused_or_cut_off_replies_are_not_shown(monkeypatch, assessed, stop):
    use(monkeypatch, FakeClient(fake_reply("Partial", stop=stop)))
    assert client.post("/api/v2/summary", json=assessed).status_code == 502


def test_api_errors_become_a_quiet_failure(monkeypatch, assessed):
    err = anthropic.APIConnectionError(request=SimpleNamespace(method="POST", url="https://api.anthropic.com"))
    use(monkeypatch, FakeClient(error=err))
    assert client.post("/api/v2/summary", json=assessed).status_code == 502


def test_switched_off_without_a_key(monkeypatch, assessed):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    fake = use(monkeypatch, FakeClient(fake_reply("x")))
    assert client.post("/api/v2/summary", json=assessed).status_code == 503
    assert fake.calls == []


def test_rate_limited_per_address(monkeypatch, assessed):
    monkeypatch.setattr(mod, "RATE_LIMIT", 2)
    use(monkeypatch, FakeClient(fake_reply("Fine.")))
    h = {"x-forwarded-for": "203.0.113.9, 10.0.0.1"}
    assert [client.post("/api/v2/summary", json=assessed, headers=h).status_code for _ in range(3)] == [200, 200, 429]
    other = {"x-forwarded-for": "198.51.100.4"}
    assert client.post("/api/v2/summary", json=assessed, headers=other).status_code == 200


def test_rate_window_expires():
    assert mod._allow("a", now=0) is True
    for _ in range(mod.RATE_LIMIT - 1):
        mod._allow("a", now=1)
    assert mod._allow("a", now=2) is False
    assert mod._allow("a", now=2 + mod.RATE_WINDOW_S) is True


def test_bad_body_is_rejected(assessed):
    assert client.post("/api/v2/summary", json={"verdict": "maybe"}).status_code == 422

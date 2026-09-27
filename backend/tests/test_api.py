"""Быстрые проверки ключевой логики. Запуск: cd backend && pytest -q  (SQLite во временной папке)."""
import os
import tempfile
from urllib.parse import quote

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.api.v1.sensors import downsample  # noqa: E402
from app.main import app  # noqa: E402

DRAFT = "observed:OBSERVED_PUMP_FLOODED_STATUS:5333:20250202T030222"


class E:  # минимальная замена TelemetryEvent
    def __init__(self, i, status):
        self.id, self.status_code, self.is_alarm = i, status, status != "normal"


def test_downsample_keeps_status_changes():
    events = [E(i, "failure" if i in (500, 501, 7000) else "normal") for i in range(10000)]
    out = downsample(events, 100)
    assert len(out) <= 100
    kept = {e.id for e in out}
    assert {0, 500, 502, 7000, 7001, 9999} <= kept  # все смены статуса + края


def test_v1_ticket_lifecycle_and_v2_decisions():
    with TestClient(app) as c:
        b, b2 = "/api/v1", "/api/v2"
        assert c.get(f"{b}/system").json()["status"] == "operational"
        pred = c.get(f"{b}/predictions/pred-847-228571").json()
        assert pred["object_id"] == 5343 and pred["risk_level"] == "critical"

        body = {"prediction_id": pred["prediction_id"], "object_id": 5343, "title": "Протяжка клемм ПК275",
                "description": "Протяжка клеммных соединений на ПК275", "assignee": "ЭТР-3"}
        t = c.post(f"{b}/tickets", json=body)
        assert t.status_code == 201
        tid = t.json()["ticket_id"]
        assert c.post(f"{b}/tickets", json=body).status_code == 409
        assert c.patch(f"{b}/tickets/{tid}/status", json={"status": "completed"}).status_code == 409
        assert c.patch(f"{b}/tickets/{tid}/status", json={"status": "approved"}).json()["status"] == "approved"

        d = quote(DRAFT, safe="")
        wo = {"draft_id": DRAFT, "work_type": "Осмотр насоса", "description": "Проверить Н3 ПК192", "idempotency_key": "wo-1"}
        assert c.post(f"{b2}/work-orders", json=wo).status_code == 409  # до утверждения
        dec = {"decision": "approved", "reason": "Проверены исходные данные", "idempotency_key": "k1"}
        first = c.post(f"{b2}/drafts/{d}/decisions", json=dec)
        assert first.status_code == 201
        assert c.post(f"{b2}/drafts/{d}/decisions", json=dec).json() == first.json()  # идемпотентность
        assert c.post(f"{b2}/drafts/{d}/decisions", json={**dec, "decision": "rejected", "idempotency_key": "k2"}).status_code == 409
        w = c.post(f"{b2}/work-orders", json=wo)
        assert w.status_code == 201
        assert c.get(f"{b2}/drafts/{d}").json()["decision"]["work_order_id"] == w.json()["work_order_id"]
        assert c.get(f"{b2}/drafts/{d}?at=2025-02-02T05:00:00Z").status_code == 422

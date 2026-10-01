from __future__ import annotations

import json
import asyncio
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True


def test_chat_headers_contain_correlation_id_and_response_time() -> None:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Hello",
                },
            )

    response = asyncio.run(send_request())
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"].startswith("req-")
    assert "x-response-time-ms" in response.headers
    assert float(response.headers["x-response-time-ms"]) >= 0


def test_chat_preserves_custom_request_id() -> None:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat",
                headers={"x-request-id": "req-custom99"},
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Hello custom",
                },
            )

    response = asyncio.run(send_request())
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-custom99"


def test_chat_logs_enrichment_and_redaction(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-pii",
                    "session_id": "session-pii",
                    "feature": "qa",
                    "message": "My email is test@vinuni.edu.vn and phone is 0987654321",
                },
            )

    response = asyncio.run(send_request())
    assert response.status_code == 200

    raw_log = log_path.read_text(encoding="utf-8")
    assert "test@vinuni.edu.vn" not in raw_log
    assert "0987654321" not in raw_log
    assert "[REDACTED_EMAIL]" in raw_log
    assert "[REDACTED_PHONE_VN]" in raw_log

    events = [json.loads(line) for line in raw_log.splitlines()]
    req_event = next(e for e in events if e["event"] == "request_received")
    assert "correlation_id" in req_event
    assert "user_id_hash" in req_event
    assert req_event["session_id"] == "session-pii"
    assert req_event["feature"] == "qa"
    assert "model" in req_event

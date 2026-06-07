import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / "n8n" / "Trackpal WhatsApp Bot.json"
)


def _workflow_nodes() -> dict[str, dict]:
    payload = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return {node["name"]: node for node in payload["nodes"]}


def test_build_result_message_sets_close_after_send_contract() -> None:
    js = _workflow_nodes()["Build result message"]["parameters"]["jsCode"]

    assert "close_after_send" in js
    assert "poll.result_type === 'code'" in js
    assert "poll.result_type === 'url'" in js
    assert "closeAfterSend = true" in js or "close_after_send: true" in js


def test_build_result_message_keeps_retry_options_for_failed_timeout() -> None:
    js = _workflow_nodes()["Build result message"]["parameters"]["jsCode"]

    assert "Could not complete code search" in js
    assert "No se pudo completar la búsqueda" in js
    assert "1️⃣ Retry" in js
    assert "2️⃣ Back to services" in js
    assert "0️⃣ Cancel" in js
    assert "1️⃣ Reintentar" in js
    assert "2️⃣ Volver a servicios" in js
    assert "0️⃣ Cancelar" in js


def test_check_close_session_reads_close_after_send_from_upstream_result() -> None:
    js = _workflow_nodes()["Check close session"]["parameters"]["jsCode"]

    assert "$('Build result message').first().json" in js
    assert "const shouldCloseAfterSend = data.close_after_send === true;" in js
    assert "if (hasLookupResult && !shouldCloseAfterSend)" in js
    assert "const isLogout = shouldCloseAfterSend" in js

import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / "n8n" / "TrackPal WhatsApp Bot.json"
)


def _workflow_payload() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _workflow_nodes() -> dict[str, dict]:
    payload = _workflow_payload()
    return {node["name"]: node for node in payload["nodes"]}


def _workflow_connections() -> dict[str, dict]:
    return _workflow_payload()["connections"]


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

    assert "try {" in js
    assert "resultData = $('Build result message').first().json" in js
    assert "catch (e)" in js
    assert "const shouldCloseAfterSend = data.close_after_send === true;" in js
    assert "if (hasLookupResult && !shouldCloseAfterSend)" in js
    assert "const isLogout = shouldCloseAfterSend" in js


def test_guard_from_me_external_non_menu_skips_without_close_contract() -> None:
    js = _workflow_nodes()["Guard fromMe external non-menu"]["parameters"]["jsCode"]

    assert "const canonicalJid = (value) => {" in js
    assert "const isMenuCommand = message === '/menu' || message === 'menu';" in js
    assert "const isRemoteCancel = message === '0';" in js
    assert "const shouldSkipBackend = Boolean(" in js
    assert "fromMe &&" in js
    assert "!isSelfTarget" in js
    assert "!isMenuCommand" in js
    assert "!isRemoteCancel" in js
    assert "skip_console_call: true" in js
    assert "no_reply: true" in js
    assert "status: 'closed'" not in js
    assert "close_jid: closeJid" not in js
    assert "close_jids: [closeJid]" not in js
    assert "guard_reason: 'from_me_external_non_menu'" in js


def test_guard_remote_cancel_reaches_backend_instead_of_skip_path() -> None:
    js = _workflow_nodes()["Guard fromMe external non-menu"]["parameters"]["jsCode"]

    assert "const isRemoteCancel = message === '0';" in js
    assert "!isRemoteCancel" in js
    assert "return [{ json: { ...input, skip_console_call: false } }];" in js


def test_guard_keeps_menu_self_target_and_missing_target_on_backend_path() -> None:
    js = _workflow_nodes()["Guard fromMe external non-menu"]["parameters"]["jsCode"]

    assert "const isSelfTarget = Boolean(" in js
    assert "targetJid &&" in js
    assert "targetJid === adminJid" in js
    assert "targetJid === remoteJid && adminJid === remoteJid" in js
    assert "return [{ json: { ...input, skip_console_call: false } }];" in js


def test_if_skip_console_call_true_branch_terminates_silently() -> None:
    node = _workflow_nodes()["IF skip console call"]
    condition = node["parameters"]["conditions"]["conditions"][0]
    connections = _workflow_connections()

    assert condition["leftValue"] == "={{ $json.skip_console_call }}"
    assert condition["operator"]["type"] == "boolean"
    assert condition["operator"]["operation"] == "true"
    assert connections["IF skip console call"]["main"][0] == []

def test_guard_connections_bypass_console_call_on_true_branch() -> None:
    connections = _workflow_connections()

    assert (
        connections["Config"]["main"][0][0]["node"] == "Guard fromMe external non-menu"
    )
    assert (
        connections["Guard fromMe external non-menu"]["main"][0][0]["node"]
        == "IF skip console call"
    )
    assert connections["IF skip console call"]["main"][0] == []
    assert connections["IF skip console call"]["main"][1][0]["node"] == "Console call"


def test_check_close_session_tolerates_guard_branch_without_merge_data() -> None:
    js = _workflow_nodes()["Check close session"]["parameters"]["jsCode"]

    assert "let fallback = {};" in js
    assert "fallback = $('Merge & lookup data').first().json;" in js
    assert "resultData = $('Build result message').first().json;" in js
    assert "const data = { ...fallback, ...resultData, ...$json };" in js


def test_parse_input_filters_not_registered_bot_echoes_without_dropping_from_me() -> (
    None
):
    js = _workflow_nodes()["Parse input"]["parameters"]["jsCode"]

    assert "no tienes una cuenta registrada" in js
    assert "you do not have a registered account" in js
    assert "if (!fromMe && looksLikeTrackPalGeneratedReply)" in js


def test_parse_input_filters_trackpal_menu_and_cancel_echoes() -> None:
    js = _workflow_nodes()["Parse input"]["parameters"]["jsCode"]

    assert "buscar codigo de acceso" in js
    assert "buscar código de acceso" in js
    assert "client console" in js
    assert "operacion cancelada" in js
    assert "operación cancelada" in js
    assert "operation cancelled" in js
    assert "find access code" in js

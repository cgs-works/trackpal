from app.services.whatsapp_navigation import (
    NAV_BACK,
    NAV_CANCEL,
    NAV_NEXT,
    ConsoleScreen,
    clear_navigation,
    current_screen,
    is_back,
    is_cancel,
    is_next,
    load_navigation,
    normalize_nav_input,
    pop_screen,
    push_screen,
    replace_screen,
)
from app.services.whatsapp_session_service import ConversationSession


def test_numeric_constants_are_strict_contract() -> None:
    assert NAV_NEXT == "8"
    assert NAV_BACK == "9"
    assert NAV_CANCEL == "0"


def test_numeric_input_classification() -> None:
    assert is_next("8") is True
    assert is_next(" 8 ") is True
    assert is_back("9") is True
    assert is_cancel("0") is True
    assert is_cancel("cancelar") is True
    assert is_cancel("salir") is True
    assert is_cancel("cerrar") is True
    assert is_cancel("9") is False
    assert is_back("0") is False
    assert is_next("9") is False
    assert is_cancel("cancel") is True
    assert is_cancel("exit") is True
    assert is_cancel("close") is True


def test_normalize_nav_input_maps_to_canonical_constants() -> None:
    assert normalize_nav_input("8") == "8"
    assert normalize_nav_input("9") == "9"
    assert normalize_nav_input("0") == "0"
    assert normalize_nav_input("cancelar") == "0"
    assert normalize_nav_input("8 ") == "8"
    assert normalize_nav_input("salir") == "0"
    assert normalize_nav_input("foo") is None
    assert normalize_nav_input(None) is None
    assert normalize_nav_input("") is None


def test_pop_screen_empty_stack_returns_none_and_does_not_clear_state() -> None:
    session = ConversationSession(phone="12015550001")
    replace_screen(session, "tenant.main")

    result = pop_screen(session)
    assert result is None
    assert current_screen(session) == ConsoleScreen(id="tenant.main", params={})


def test_push_replace_pop_navigation_stack() -> None:
    session = ConversationSession(phone="12015550001")

    replace_screen(session, "tenant.main")
    assert current_screen(session) == ConsoleScreen(id="tenant.main", params={})

    push_screen(session, "tenant.clients.menu")
    assert current_screen(session) == ConsoleScreen(id="tenant.clients.menu", params={})
    state = load_navigation(session)
    assert state.stack == [ConsoleScreen(id="tenant.main", params={})]

    push_screen(session, "tenant.clients.detail", client_id="abc")
    assert current_screen(session) == ConsoleScreen(
        id="tenant.clients.detail", params={"client_id": "abc"}
    )

    previous = pop_screen(session)
    assert previous == ConsoleScreen(id="tenant.clients.menu", params={})
    assert current_screen(session) == ConsoleScreen(id="tenant.clients.menu", params={})

    previous = pop_screen(session)
    assert previous == ConsoleScreen(id="tenant.main", params={})
    assert current_screen(session) == ConsoleScreen(id="tenant.main", params={})


def test_clear_navigation_removes_private_temp_data_key() -> None:
    session = ConversationSession(phone="12015550001")
    replace_screen(session, "tenant.main")
    push_screen(session, "tenant.clients.menu")

    clear_navigation(session)

    assert "_nav" not in session.temp_data
    assert current_screen(session) is None


def test_nav_state_survives_round_trip_serialization() -> None:
    session = ConversationSession(phone="12015550001")
    replace_screen(session, "tenant.main")
    push_screen(session, "tenant.clients.menu")
    push_screen(session, "tenant.clients.detail", client_id="abc")

    raw = session.model_dump()
    restored = ConversationSession(**raw)

    assert current_screen(restored) == ConsoleScreen(
        id="tenant.clients.detail", params={"client_id": "abc"}
    )
    nav = load_navigation(restored)
    assert nav.stack == [
        ConsoleScreen(id="tenant.main", params={}),
        ConsoleScreen(id="tenant.clients.menu", params={}),
    ]

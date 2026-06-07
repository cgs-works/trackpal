"""Tests for ContingencyReplyPolicy — degraded-state reply texts."""

from app.services.contingency_reply_policy import ContingencyReplyPolicy


class TestContingencyReplyPolicy:
    """Verify reply texts are well-formed, in Spanish, and relayable."""

    def test_session_reset_is_not_empty(self) -> None:
        assert ContingencyReplyPolicy.SESSION_RESET
        assert len(ContingencyReplyPolicy.SESSION_RESET) > 50

    def test_session_reset_mentions_contingency(self) -> None:
        text = ContingencyReplyPolicy.SESSION_RESET.lower()
        assert "contingencia" in text

    def test_session_reset_asks_user_to_choose(self) -> None:
        text = ContingencyReplyPolicy.SESSION_RESET.lower()
        assert "selecciona" in text or "elige" in text or "opción" in text

    def test_session_reset_includes_menu(self) -> None:
        text = ContingencyReplyPolicy.SESSION_RESET
        assert "Ver empresas" in text
        assert "Crear empresa" in text

    def test_temporary_unavailable_is_not_empty(self) -> None:
        assert ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE
        assert len(ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE) > 20

    def test_temporary_unavailable_mentions_unavailable(self) -> None:
        text = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE.lower()
        assert "no disponible" in text

    def test_temporary_unavailable_says_to_retry(self) -> None:
        text = ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE.lower()
        assert "intenta" in text or "nuevamente" in text

    def test_both_replies_are_strings(self) -> None:
        assert isinstance(ContingencyReplyPolicy.SESSION_RESET, str)
        assert isinstance(ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE, str)

    def test_session_reset_differs_from_temporary_unavailable(self) -> None:
        assert ContingencyReplyPolicy.SESSION_RESET != ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE

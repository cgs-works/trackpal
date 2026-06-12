"""Profile flow handlers for the Tenant Console."""

from __future__ import annotations

from typing import Any

from app.core.errors import UserFacingError, translate_error
from app.core.i18n import LOCALE_NAMES, t as _i18n_t
from app.repositories import tenants_repository
from app.schemas.tenant_settings import TenantSettingsUpdate
from app.services.tenant_settings_service import TenantSettingsService
from app.services.whatsapp_navigation import is_back

from . import _context as ctx


async def _start_profile_flow(
    self, phone: str, session_service: Any, user_id: Any, db: Any
) -> str:
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.PROFILE_FLOW
        session.step = self.PROFILE_STEP_ACTION
        session.temp_data = {}
        await session_service.save_session(session)
    return self._t(self.KEY_PROFILE_MENU)


async def _handle_profile_action(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    user_id: Any,
    db: Any,
) -> str:
    if msg == "1":
        return await self._show_profile(phone, session_service, user_id, db)
    elif msg == "2":
        return await self._start_profile_edit(phone, session, session_service)
    elif msg == "3":
        return await self._start_profile_change_password(
            phone, session, session_service
        )
    elif msg == "4":
        return await self._start_profile_change_locale(phone, session, session_service)
    elif is_back(msg):
        return self._with_main_menu("")
    return self._t(self.KEY_FALLBACK_NO_FLOW)


async def _show_profile(self, phone, session_service, user_id, db):
    if user_id is None or db is None or self._profile_service is None:
        return self._t("wa.tenant.errors.profile_load_failed")
    from app.repositories import users_repository

    user = await users_repository.get(db, user_id)
    if user is None:
        return self._t("wa.tenant.errors.user_not_found")
    profile = await self._profile_service.get_profile(db, user)
    if profile is None:
        return self._t("wa.tenant.errors.profile_not_found")
    return self._format_profile_detail(profile, user.username)


async def _start_profile_edit(
    self, phone: str, session: Any, session_service: Any
) -> str:
    session.flow = self.PROFILE_FLOW
    session.step = self.PROFILE_STEP_EDIT_FIELD
    session.temp_data = {}
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_PROFILE_EDIT_FIELD_PROMPT)


async def _handle_profile_edit_field(
    self, phone: str, msg: str, session: Any, session_service: Any
) -> str:
    if is_back(msg):
        await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    field = self.PROFILE_EDIT_FIELD_MAP.get(msg)
    if field is None:
        return self._t(self.KEY_PROFILE_EDIT_ERROR_INVALID_FIELD)
    session.temp_data["field"] = field
    session.step = self.PROFILE_STEP_EDIT_VALUE
    if session_service is not None:
        await session_service.save_session(session)
    return self.PROFILE_EDIT_PROMPTS[field]


async def _handle_profile_edit_value(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    user_id: Any,
    db: Any,
) -> str:
    field = session.temp_data.get("field", "")
    new_value = msg.strip()
    if user_id is None or db is None or self._profile_service is None:
        return self._t("wa.tenant.errors.profile_update_failed")
    from app.repositories import users_repository

    user = await users_repository.get(db, user_id)
    if user is None:
        return self._t("wa.tenant.errors.user_not_found")
    from app.schemas.me import ProfileUpdate

    payload = ProfileUpdate(**{field: new_value})
    try:
        profile = await self._profile_service.update_profile(db, user, payload)
    except UserFacingError as exc:
        return "❌ " + translate_error(ctx.get_locale(), exc)
    except ValueError as exc:
        return "❌ " + str(exc)
    if profile is None:
        return self._t("wa.tenant.errors.profile_update_failed")
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return (
        self._with_main_menu(self._t(self.KEY_PROFILE_EDIT_SUCCESS))
        + self._post_action_prompt()
    )


async def _start_profile_change_password(
    self, phone: str, session: Any, session_service: Any
) -> str:
    session.flow = self.PROFILE_FLOW
    session.step = self.PROFILE_STEP_CHANGE_PASSWORD_OLD
    session.temp_data = {}
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_PROFILE_CHANGE_PASSWORD_PROMPT_OLD)


async def _handle_profile_change_password_old(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    user_id: Any,
    db: Any,
) -> str:
    old_password = msg.strip()
    if not old_password:
        return self._t(self.KEY_PROFILE_CHANGE_PASSWORD_PROMPT_OLD)
    session.temp_data["old_password"] = old_password
    session.step = self.PROFILE_STEP_CHANGE_PASSWORD_NEW
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_PROFILE_CHANGE_PASSWORD_PROMPT_NEW)


async def _handle_profile_change_password_new(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    user_id: Any,
    db: Any,
) -> str:
    new_password = msg.strip()
    old_password = session.temp_data.get("old_password", "")
    if len(new_password) < 6:
        return (
            self._t("wa.tenant.errors.password_short")
            + "\n\n"
            + self._t(self.KEY_PROFILE_CHANGE_PASSWORD_PROMPT_NEW)
        )
    if user_id is None or db is None or self._profile_service is None:
        return self._t("wa.tenant.errors.password_change_failed")
    from app.repositories import users_repository

    user = await users_repository.get(db, user_id)
    if user is None:
        return self._t("wa.tenant.errors.user_not_found")
    success = await self._profile_service.change_password(
        db, user, old_password, new_password
    )
    if not success:
        return self._t(self.KEY_PROFILE_CHANGE_PASSWORD_ERROR_OLD)
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return (
        self._with_main_menu(self._t(self.KEY_PROFILE_CHANGE_PASSWORD_SUCCESS))
        + self._post_action_prompt()
    )


async def _start_profile_change_locale(
    self, phone: str, session: Any, session_service: Any
) -> str:
    current_locale = ctx.get_locale()
    current_locale_name = LOCALE_NAMES.get(current_locale, current_locale)
    if session_service is not None:
        session.flow = self.PROFILE_FLOW
        session.step = self.PROFILE_STEP_CHANGE_LOCALE_SELECT
        await session_service.save_session(session)
    return self._t(self.KEY_PROFILE_LOCALE_SELECT, current_locale=current_locale_name)


async def _handle_profile_change_locale_select(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    user_id: Any,
    db: Any,
) -> str:
    if is_back(msg):
        return self._with_main_menu("")
    if msg not in ("1", "2"):
        return self._t(self.KEY_FALLBACK_NO_FLOW)

    new_locale = "en" if msg == "1" else "es"

    if user_id is not None and db is not None:
        tenant = await tenants_repository.get_by_owner(db, user_id)
        if tenant is not None:
            service = TenantSettingsService()
            await service.update_settings(
                db,
                tenant.id,
                TenantSettingsUpdate(locale=new_locale),
            )

    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")

    token = ctx.set_locale(new_locale)
    try:
        human_name = LOCALE_NAMES.get(new_locale, new_locale)
        return (
            self._with_main_menu(
                _i18n_t(
                    new_locale,
                    "wa.tenant.profile.locale_changed",
                    locale_name=human_name,
                )
            )
            + self._post_action_prompt()
        )
    finally:
        ctx.reset_locale(token)

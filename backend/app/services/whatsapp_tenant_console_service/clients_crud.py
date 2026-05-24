"""Client create/edit/lifecycle handlers."""

from app.core.errors import UserFacingError, translate_error

from . import _context as ctx


async def _start_client_create(self, phone, session_service):
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.CLIENTS_FLOW
        session.step = self.CLIENTS_STEP_CREATE_FULL_NAME
        session.temp_data = {}
        await session_service.save_session(session)
    return self._t(self.KEY_CLIENT_CREATE_PROMPT_FULL_NAME)


async def _handle_client_create_full_name(self, phone, msg, session, session_service):
    name = msg.strip()
    if not name:
        return self._t(self.KEY_CLIENT_NAME_REQUIRED)
    session.temp_data["full_name"] = name
    session.step = self.CLIENTS_STEP_CREATE_PHONE
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_CLIENT_CREATE_PROMPT_PHONE)


async def _handle_client_create_phone(self, phone, msg, session, session_service):
    stripped = msg.strip()
    if not stripped or stripped.lower() in self.CLIENT_SKIP_WORDS:
        session.temp_data["phone"] = None
    else:
        from app.core.input_validation import validate_phone
        try:
            normalized = validate_phone(stripped, required=False)
            session.temp_data["phone"] = normalized
        except Exception:
            return self._t(self.KEY_CLIENT_CREATE_ERROR_PHONE)
    session.step = self.CLIENTS_STEP_CREATE_USERNAME
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_CLIENT_CREATE_PROMPT_USERNAME)


async def _handle_client_create_username(self, phone, msg, session, session_service):
    username = msg.strip()
    if not username:
        return self._t(self.KEY_CLIENT_USERNAME_REQUIRED)
    session.temp_data["local_username"] = username.lower()
    session.step = self.CLIENTS_STEP_CREATE_PASSWORD
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_CLIENT_CREATE_PROMPT_PASSWORD)


async def _handle_client_create_password(self, phone, msg, session, session_service):
    password = msg.strip()
    if len(password) < 6:
        return self._t(self.KEY_CLIENT_SHORT_PASSWORD)
    session.temp_data["password"] = password
    session.step = self.CLIENTS_STEP_CREATE_CONFIRM
    if session_service is not None:
        await session_service.save_session(session)
    data = session.temp_data
    return self._t(self.KEY_CLIENT_CREATE_CONFIRM_TEMPLATE,
        name=data.get("full_name", ""),
        username=data.get("local_username", ""),
        phone=data.get("phone") or "—",
    )


async def _handle_client_create_confirm(self, phone, msg, session, session_service, tenant_id, db):
    stripped = msg.strip()
    if stripped.upper() not in ("CONFIRMAR", "CONFIRM"):
        data = session.temp_data
        return (
            self._t(self.KEY_CLIENT_CONFIRM_REPROMPT) + "\n\n"
            + self._t(self.KEY_CLIENT_CREATE_CONFIRM_TEMPLATE,
                name=data.get("full_name", ""),
                username=data.get("local_username", ""),
                phone=data.get("phone") or "—",
            )
        )
    data = session.temp_data
    if tenant_id is None or db is None or self._client_service is None:
        return self._t("wa.tenant.errors.client_create_service_unavailable")

    from app.schemas.client import ClientCreate

    payload = ClientCreate(
        full_name=data.get("full_name", ""),
        local_username=data.get("local_username", ""),
        phone=data.get("phone"),
        password=data.get("password", ""),
    )
    try:
        client = await self._client_service.create_client(db, tenant_id, payload)
    except UserFacingError as exc:
        error = translate_error(ctx.get_locale(), exc)
        if exc.code in {"phone_already_registered", "client_local_username_exists", "username_already_registered"}:
            if exc.code == "phone_already_registered":
                session.step = self.CLIENTS_STEP_CREATE_PHONE
                if session_service is not None:
                    await session_service.save_session(session)
                return "❌ " + error + "\n\n" + self._t(self.KEY_CLIENT_CREATE_PROMPT_PHONE)
            session.step = self.CLIENTS_STEP_CREATE_USERNAME
            if session_service is not None:
                await session_service.save_session(session)
            return "❌ " + error + "\n\n" + self._t(self.KEY_CLIENT_CREATE_PROMPT_USERNAME)
        return "❌ " + error
    except ValueError as exc:
        error = str(exc)
        if "phone" in error.lower() or "teléfono" in error.lower():
            session.step = self.CLIENTS_STEP_CREATE_PHONE
            if session_service is not None:
                await session_service.save_session(session)
            return "❌ " + error + "\n\n" + self._t(self.KEY_CLIENT_CREATE_PROMPT_PHONE)
        if "username" in error.lower() or "usuario" in error.lower():
            session.step = self.CLIENTS_STEP_CREATE_USERNAME
            if session_service is not None:
                await session_service.save_session(session)
            return "❌ " + error + "\n\n" + self._t(self.KEY_CLIENT_CREATE_PROMPT_USERNAME)
        return "❌ " + error

    if client is None:
        return self._t("wa.tenant.errors.client_create_failed_generic")

    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")

    full_username = getattr(client.user, "username", data.get("local_username", ""))
    return self._with_main_menu(
        self._t(self.KEY_CLIENT_CREATE_SUCCESS,
            name=client.full_name,
            username_full=full_username,
            phone=client.phone or "—",
        )
    )


async def _start_client_edit(self, phone, session, session_service):
    session.flow = self.CLIENTS_FLOW
    session.step = self.CLIENTS_STEP_EDIT_FIELD
    session.temp_data = {}
    if session_service is not None:
        await session_service.save_session(session)
    return self._t(self.KEY_CLIENT_EDIT_FIELD_PROMPT)


async def _handle_client_edit_field(self, phone, msg, session, session_service):
    if msg == "0":
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    field = self.CLIENT_EDIT_FIELD_MAP.get(msg)
    if field is None:
        return self._t(self.KEY_CLIENT_EDIT_ERROR_INVALID_FIELD)
    session.temp_data["field"] = field
    session.step = self.CLIENTS_STEP_EDIT_VALUE
    if session_service is not None:
        await session_service.save_session(session)
    return self.CLIENT_EDIT_PROMPTS[field]


async def _handle_client_edit_value(self, phone, msg, session, session_service, tenant_id, db):
    field = session.temp_data.get("field", "")
    new_value = msg.strip()
    client_id = session.selected_tenant_id
    if not client_id or tenant_id is None or db is None or self._client_service is None:
        return self._t("wa.tenant.errors.client_update_failed")
    parsed_id = self._safe_uuid(client_id)
    if parsed_id is None:
        return self._t("wa.tenant.errors.client_update_failed")

    from app.schemas.client import ClientUpdate
    payload = ClientUpdate(**{field: new_value})
    try:
        client = await self._client_service.update_client(db, tenant_id, parsed_id, payload)
    except UserFacingError as exc:
        return "❌ " + translate_error(ctx.get_locale(), exc)
    except ValueError as exc:
        return "❌ " + str(exc)
    except Exception as exc:
        return "❌ " + str(exc)

    if client is None:
        return self._t("wa.tenant.errors.client_not_found")

    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(
        self._t(self.KEY_CLIENT_EDIT_SUCCESS, name=client.full_name)
    )


async def _handle_client_deactivate_confirm(self, phone, msg, session, session_service, tenant_id, db):
    stripped = msg.strip()
    if stripped.upper() not in ("CONFIRMAR", "CONFIRM"):
        return self._t(self.KEY_CLIENT_CONFIRM_REPROMPT)
    client_id = session.selected_tenant_id
    if not client_id or tenant_id is None or db is None or self._client_service is None:
        return self._t("wa.tenant.errors.client_deactivate_failed")
    parsed_id = self._safe_uuid(client_id)
    if parsed_id is None:
        return self._t("wa.tenant.errors.client_deactivate_failed")
    client = await self._client_service.deactivate_client(db, tenant_id, parsed_id)
    if client is None:
        return self._t("wa.tenant.errors.client_not_found")
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(
        self._t(self.KEY_CLIENT_DEACTIVATE_SUCCESS, name=client.full_name)
    )


async def _handle_client_delete_confirm(self, phone, msg, session, session_service, tenant_id, db):
    stripped = msg.strip()
    if stripped.upper() not in ("CONFIRMAR", "CONFIRM"):
        return self._t(self.KEY_CLIENT_CONFIRM_REPROMPT)
    client_id = session.selected_tenant_id
    if not client_id or tenant_id is None or db is None or self._client_service is None:
        return self._t("wa.tenant.errors.client_delete_failed")
    parsed_id = self._safe_uuid(client_id)
    if parsed_id is None:
        return self._t("wa.tenant.errors.client_delete_failed")
    client_name = client_id
    client = await self._client_service.get_client(db, tenant_id, parsed_id)
    if client:
        client_name = client.full_name
    deleted = await self._client_service.delete_client(db, tenant_id, parsed_id)
    if not deleted:
        return self._t("wa.tenant.errors.client_delete_failed")
    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(
        self._t(self.KEY_CLIENT_DELETE_SUCCESS, name=client_name)
    )

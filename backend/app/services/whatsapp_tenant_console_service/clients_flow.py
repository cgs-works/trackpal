"""Client flow handlers for the Tenant Console."""

from __future__ import annotations





async def _start_clients_flow(self, phone, session_service, tenant_id, db):
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.CLIENTS_FLOW
        session.step = self.CLIENTS_STEP_LIST
        session.temp_data = {}
        await session_service.save_session(session)
    return self._t(self.KEY_CLIENTS_MENU)


async def _handle_client_list_selection(self, phone, msg, session, session_service, tenant_id, db):
    if msg == "1":
        if tenant_id is None or db is None or self._client_service is None:
            return self._t(self.KEY_CLIENT_NO_CLIENTS)
        clients = await self._client_service.list_clients(db, tenant_id)
        if not clients:
            return self._with_main_menu(self._t(self.KEY_CLIENT_NO_CLIENTS))
        reply, selection_map = self._format_client_list(clients)
        reply += "\n\n" + self._t(self.KEY_CLIENT_SELECT_PROMPT)
        if session_service is not None:
            session.flow = self.CLIENTS_FLOW
            session.step = self.CLIENTS_STEP_SELECT
            session.selection_map = selection_map
            await session_service.save_session(session)
        return reply
    elif msg == "2":
        return await self._start_client_create(phone, session_service)
    elif msg == "3":
        return await self._handle_clients_block_list(
            phone, msg, session, session_service, tenant_id, db
        )
    elif msg == "9":
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu("")
    else:
        client_id = session.selection_map.get(msg)
        if client_id:
            if db is None or self._client_service is None:
                return self._t(self.KEY_CLIENT_INVALID_SELECTION)
            parsed_id = self._safe_uuid(client_id)
            if parsed_id is None:
                return self._t(self.KEY_CLIENT_INVALID_SELECTION)
            client = await self._client_service.get_client(db, tenant_id, parsed_id)
            if client:
                reply = self._format_client_detail(client)
                if session_service is not None:
                    session.selected_tenant_id = client_id
                    session.step = self.CLIENTS_STEP_DETAIL_ACTION
                    await session_service.save_session(session)
                return reply
        return self._t(self.KEY_CLIENT_INVALID_SELECTION)


async def _handle_client_select(self, phone, msg, session, session_service, tenant_id, db):
    client_id = session.selection_map.get(msg)
    if client_id:
        if db is None or self._client_service is None:
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)
        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)
        client = await self._client_service.get_client(db, tenant_id, parsed_id)
        if client:
            reply = self._format_client_detail(client)
            if session_service is not None:
                session.selected_tenant_id = client_id
                session.step = self.CLIENTS_STEP_DETAIL_ACTION
                await session_service.save_session(session)
            return reply
    return self._t(self.KEY_CLIENT_INVALID_SELECTION)


async def _handle_client_detail_action(self, phone, msg, session, session_service, tenant_id, db):
    client_id = session.selected_tenant_id
    if not client_id:
        return self._t(self.KEY_CLIENT_INVALID_SELECTION)

    parsed_id = self._safe_uuid(client_id)
    if parsed_id is None:
        return self._t(self.KEY_CLIENT_INVALID_SELECTION)

    if msg == "1":
        return await self._start_client_edit(phone, session, session_service)
    elif msg == "2":
        if db is None or self._client_service is None:
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)
        client = await self._client_service.get_client(db, tenant_id, parsed_id)
        if client is None:
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)
        if client.is_active:
            session.flow = self.CLIENTS_FLOW
            session.step = self.CLIENTS_STEP_DEACTIVATE_CONFIRM
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_CLIENT_DEACTIVATE_CONFIRM_TEMPLATE, name=client.full_name)
        else:
            await self._client_service.activate_client(db, tenant_id, parsed_id)
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self._with_main_menu(
                self._t(self.KEY_CLIENT_REACTIVATE_SUCCESS, name=client.full_name)
            )
    elif msg == "3":
        if db is None or self._client_service is None:
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)
        client = await self._client_service.get_client(db, tenant_id, parsed_id)
        if client is None:
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)
        if client.is_active:
            return self._t(self.KEY_CLIENT_CANT_DELETE_ACTIVE)
        session.flow = self.CLIENTS_FLOW
        session.step = self.CLIENTS_STEP_DELETE_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CLIENT_DELETE_CONFIRM_TEMPLATE, name=client.full_name)
    elif msg == "0":
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_MAIN_MENU)
    return ""


async def _handle_clients_block_list(
    self, phone, msg, session, session_service, tenant_id, db
):
    from app.repositories import client_messaging_block_repository

    if db is None:
        return self._t(self.KEY_CLIENT_BLOCK_LIST_EMPTY)
    blocks = await client_messaging_block_repository.list_active(db, tenant_id)
    if not blocks:
        return self._t(self.KEY_CLIENT_BLOCK_LIST_EMPTY)

    lines: list[str] = []
    selection_map: dict[str, str] = {}
    for i, block in enumerate(blocks, start=1):
        identity = block.phone or block.whatsapp_lid or "—"
        lines.append(f"{i}️⃣ {identity}")
        selection_map[str(i)] = str(block.id)

    reply = self._t(self.KEY_CLIENT_BLOCK_LIST_HEADER) + "\n".join(lines)
    reply += "\n\n" + self._t(self.KEY_CLIENT_BLOCK_UNBLOCK_PROMPT)

    if session_service is not None:
        session.flow = self.CLIENTS_FLOW
        session.step = self.CLIENTS_STEP_BLOCK_LIST
        session.selection_map = selection_map
        await session_service.save_session(session)

    return reply


async def _handle_clients_block_unblock(
    self, phone, msg, session, session_service, tenant_id, db,
):
    from app.repositories import client_messaging_block_repository

    if msg == "0":
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_CLIENTS_MENU)

    block_id = session.selection_map.get(msg)
    if not block_id or db is None:
        return self._t(self.KEY_CLIENT_BLOCK_INVALID_SELECTION)

    parsed_id = self._safe_uuid(block_id)
    if parsed_id is None:
        return self._t(self.KEY_CLIENT_BLOCK_INVALID_SELECTION)

    block = await client_messaging_block_repository.unblock(db, tenant_id, parsed_id)
    if block is None:
        return self._t(self.KEY_CLIENT_BLOCK_INVALID_SELECTION)

    identity = block.phone or block.whatsapp_lid or "—"

    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")

    return self._with_main_menu(
        self._t(self.KEY_CLIENT_BLOCK_UNBLOCK_SUCCESS, identity=identity)
    )

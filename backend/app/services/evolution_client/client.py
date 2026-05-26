import secrets
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = __import__("logging").getLogger(__name__)


class EvolutionClient:
    def __init__(
        self,
        base_url: str = settings.evolution_api_url,
        api_key: str = settings.evolution_api_key,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _instance_name(self, instance_name: str) -> str:
        return instance_name if instance_name.startswith("tenant-") else f"tenant-{instance_name}"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "apikey": self.api_key}

    async def create_instance(self, instance_name: str) -> dict[str, str] | None:
        if not self.api_key or not self.base_url:
            logger.warning(
                "Evolution API not configured; skipping instance creation for %s",
                instance_name,
            )
            return None

        evolution_instance_name = self._instance_name(instance_name)
        instance_token = secrets.token_urlsafe(32)
        payload = {
            "name": evolution_instance_name,
            "token": instance_token,
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = await client.post(
                "/instance/create", json=payload, headers=self._headers
            )
            response.raise_for_status()
            data = self._response_data(response.json())
            instance_id = self._instance_id(data)
            if not instance_id:
                instance_id = await self._find_instance_id(client, evolution_instance_name)
        logger.info("Evolution instance created: %s", evolution_instance_name)

        if not instance_id:
            raise ValueError("Evolution instance id not found after create")

        return {
            "instance_id": instance_id,
            "instance_token": instance_token,
        }

    async def register_webhook(self, instance_id: str) -> None:
        if not self.api_key or not self.base_url:
            logger.warning(
                "Evolution API not configured; skipping webhook registration for %s",
                instance_id,
            )
            return

        payload = {
            "enabled": True,
            "webhookUrl": "https://rs-n8n.wilfredocamacho.dev/webhook/trackpalmastertenantclient",
            "triggerType": "keyword",
            "triggerOperator": "startsWith",
            "triggerValue": "/menu",
            "isTrusted": True,
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            create_response = await client.post(
                f"/webhook/create/{quote(instance_id, safe='')}",
                json=payload,
                headers=self._headers,
            )
            if create_response.status_code >= 400:
                find_response = await client.get(
                    f"/webhook/find/{quote(instance_id, safe='')}",
                    headers=self._headers,
                )
                find_response.raise_for_status()
                webhooks = self._response_data(find_response.json())
                if not isinstance(webhooks, list):
                    webhooks = []

                target_webhook = next(
                    (w for w in webhooks if w.get("webhookUrl") == payload["webhookUrl"]),
                    None,
                )
                if not target_webhook and webhooks:
                    target_webhook = webhooks[0]

                if target_webhook and "id" in target_webhook:
                    update_response = await client.put(
                        f"/webhook/update/{quote(target_webhook['id'], safe='')}",
                        json=payload,
                        headers=self._headers,
                    )
                    update_response.raise_for_status()
                else:
                    create_response.raise_for_status()
                    
        logger.info("Webhook configured for instance ID: %s", instance_id)

    async def delete_instance(self, instance_name: str) -> None:
        if not self.api_key or not self.base_url:
            logger.warning(
                "Evolution API not configured; skipping instance deletion for %s",
                instance_name,
            )
            return

        evolution_instance_name = self._instance_name(instance_name)
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            instance_id = await self._find_instance_id(
                client, evolution_instance_name
            )
            if not instance_id:
                logger.warning(
                    "Evolution instance not found (already deleted): %s",
                    evolution_instance_name,
                )
                return

            response = await client.delete(
                f"/instance/delete/{quote(instance_id, safe='')}",
                headers=self._headers,
            )
            if response.status_code == 404:
                logger.warning(
                    "Evolution instance not found (already deleted): %s",
                    evolution_instance_name,
                )
                return
            response.raise_for_status()
        logger.info("Evolution instance deleted: %s", evolution_instance_name)

    async def _find_instance_id(
        self, client: httpx.AsyncClient, evolution_instance_name: str
    ) -> str:
        response = await client.get("/instance/all", headers=self._headers)
        response.raise_for_status()
        instances = self._response_data(response.json())
        if not isinstance(instances, list):
            return ""
        match = next(
            (
                instance
                for instance in instances
                if instance.get("name") == evolution_instance_name
                or instance.get("instanceName") == evolution_instance_name
            ),
            None,
        )
        return self._instance_id(match or {})

    def _response_data(self, data: Any) -> Any:
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    def _instance_id(self, data: Any) -> str:
        if not isinstance(data, dict):
            return ""
        instance = data.get("instance")
        if isinstance(instance, dict):
            data = {**data, **instance}
        value = data.get("id") or data.get("instanceId")
        return str(value) if value else ""

    async def close_chat_session(
        self, *, instance: str, remote_jid: str
    ) -> None:
        """Deprecated: Cierre de sesión ahora se gestiona directamente desde n8n
        vía `POST /webhook/change-status`. Se mantiene temporalmente como no-op
        para evitar romper llamadas heredadas hasta que se limpien.
        """
        logger.warning(
            "close_chat_session is deprecated. Session closing is now handled by n8n. "
            "Call ignored for instance=%s remoteJid=%s",
            instance,
            remote_jid,
        )


evolution_client = EvolutionClient()

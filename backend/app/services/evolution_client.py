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

    async def create_instance(self, instance_name: str) -> None:
        if not self.api_key:
            logger.warning(
                "EVOLUTION_API_KEY not configured; skipping instance creation for %s",
                instance_name,
            )
            return

        evolution_instance_name = self._instance_name(instance_name)
        payload = {
            "instanceName": evolution_instance_name,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
            "rejectCall": True,
            "alwaysOnline": True,
            "readMessages": True,
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = await client.post(
                "/instance/create", json=payload, headers=self._headers
            )
            response.raise_for_status()
        logger.info("Evolution instance created: %s", evolution_instance_name)

    async def setup_n8n_integration(self, instance_name: str) -> None:
        if not self.api_key:
            logger.warning(
                "EVOLUTION_API_KEY not configured; skipping n8n integration for %s",
                instance_name,
            )
            return

        evolution_instance_name = self._instance_name(instance_name)
        payload = {
            "enabled": True,
            "webhookUrl": "https://rs-n8n.wilfredocamacho.dev/webhook/trackpal-whatsapp-bot",
            "triggerType": "keyword",
            "triggerOperator": "startsWith",
            "triggerValue": "/menu",
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = await client.post(
                f"/n8n/create/{quote(evolution_instance_name, safe='')}",
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
        logger.info("n8n integration configured for instance: %s", evolution_instance_name)


evolution_client = EvolutionClient()

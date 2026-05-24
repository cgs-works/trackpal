"""Client service — tenant-scoped client CRUD and lifecycle."""

from .service import ClientService, build_client_username

__all__ = ["ClientService", "build_client_username"]

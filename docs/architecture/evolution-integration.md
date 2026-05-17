# Evolution API Integration

The backend integrates with Evolution API (WhatsApp Business API proxy) for instance management and chat session control.

## Client (`app/services/evolution_client.py`)

`EvolutionClient` is a singleton instantiated at module level as `evolution_client`.

### Instance Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `create_instance(name)` | `POST /instance/create` | Creates WhatsApp instance with Baileys integration |
| `setup_n8n_integration(name)` | `POST /n8n/create/{name}` | Configures n8n webhook for inbound messages |
| `delete_instance(name)` | `DELETE /instance/delete/{name}` | Removes instance; 404 is handled gracefully |

Instance names are prefixed with `tenant-` automatically (e.g., `tenant-acme`).

### Chat Session Control

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `close_chat_session(instance, remote_jid)` | `POST /n8n/changeStatus/{instance}` | Marks chat as `closed` on master logout |

### Configuration

- `EVOLUTION_API_URL` — Base URL (e.g., `https://rs-evoapi.wilfredocamacho.dev`)
- `EVOLUTION_API_KEY` — API key for authentication (sent as `apikey` header)

When API key or URL are empty, all methods are no-ops with a warning log. This enables testing without Evolution API.

### Tenant Lifecycle Integration

- **Create tenant**: `create_instance` + `setup_n8n_integration` are called inside `TenantService.create_tenant()`. If Evolution API calls fail, the tenant creation is rolled back.
- **Delete tenant**: `delete_instance` is called inside `TenantService.delete_tenant()`. The tenant must be inactive before deletion.
- **Update tenant**: Changing `evolution_instance_name` only updates the database value; it does NOT recreate or rename the instance in Evolution API.

# Deploy

## Backend (Render)

### Via Render Blueprint (automated)

El archivo `render.yaml` en la raíz permite deploy automático conectando el repo de GitHub a Render.

### Via Render Dashboard (manual)

1. Crear **Web Service** en [dashboard.render.com](https://dashboard.render.com)
2. Conectar repositorio `github.com/neutrobox/trackpal`
3. Configurar:
   - **Name**: `trackpal-api`
   - **Runtime**: `Python`
   - **Root Directory**: `backend` (importante — Render ejecutará todo desde allí)
   - **Build Command**: `pip install uv && uv sync`
   - **Start Command**: `uv run alembic upgrade head && uv run python -m scripts.seed && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free

### Environment Variables (Render)

| Variable | Valor | Notas |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Usar session pooler de Supabase con `?sslmode=require` |
| `SECRET_KEY` | `<generated>` | Render puede auto-generarlo |
| `N8N_API_KEY` | `<tu-api-key>` | Misma que usás en n8n |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `MASTER_USERNAME` | `master` | |
| `MASTER_PASSWORD` | `<tu-password>` | Para el seed del Master |
| `MASTER_NAME` | `Master Trackpal` | |
| `MASTER_PHONE` | `+521234567890` | Tu WhatsApp conectado a Evolution API |
| `REDIS_PRIMARY_URL` | `redis://...` | Redis principal (obligatorio para HA). Soporta `redis://` y `rediss://` |
| `REDIS_BACKUP_URL` | `redis://...` | Redis backup (opcional, para failover HA). Soporta `redis://` y `rediss://` |
| `REDIS_POOL_SIZE` | `20` | Conexiones máximas por pool |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | `5.0` | Timeout de socket Redis |
| `REDIS_CONNECT_TIMEOUT_SECONDS` | `5.0` | Timeout de conexión Redis |
| `REDIS_HEALTH_CHECK_INTERVAL_SECONDS` | `30.0` | Intervalo health check Redis |
| `REDIS_FAILOVER_FAILURE_THRESHOLD` | `3` | Fallos consecutivos antes de failover |
| `REDIS_BREAKER_OPEN_SECONDS` | `30` | Ventana breaker abierto (segundos) |
| `WHATSAPP_SESSION_TTL_MINUTES` | `15` | TTL de sesión conversacional |
| `WHATSAPP_AUTH_FAIL_THRESHOLD` | `5` | Intentos fallidos antes de bloqueo temporal |
| `WHATSAPP_AUTH_LOCK_MINUTES` | `5` | Duración del bloqueo temporal (minutos) |
| `WHATSAPP_AUTH_FAIL_WINDOW_MINUTES` | `15` | Ventana de contador de fallos (minutos) |

### Post-deploy

Render ejecuta automáticamente desde `backend/` (por el Root Directory):
1. `pip install uv && uv sync` (instalar dependencias)
2. `uv run alembic upgrade head` (migraciones)
3. `uv run python scripts/seed.py` (seed del Master)
4. `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT` (servidor)
```bash
# Si Render tiene shell:
uv run python scripts/seed.py

# O desde local contra la DB de producción:
uv run python scripts/seed.py
```

La URL final será: `https://trackpal-api.onrender.com`

---

## Frontend (Cloudflare Pages)

### Configuración

1. Ir a [dash.cloudflare.com](https://dash.cloudflare.com) → Pages → Create a project
2. Conectar repositorio `github.com/neutrobox/trackpal`
3. Configurar build:
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Root directory**: `frontend`

### Environment Variables (Cloudflare Pages)

| Variable | Valor |
|---|---|
| `VITE_API_URL` | `https://trackpal-api.onrender.com/api/v1` |

El archivo `frontend/public/_redirects` ya está configurado para SPA routing (todas las rutas → index.html).

### Post-deploy

La URL será similar a: `https://trackpal.pages.dev`

---

## n8n Workflow

El workflow export (`n8n/Trackpal WhatsApp Bot.json`) usa `{{$env.*}}` expressions para evitar secretos en repositorio.

> **Nota sobre licencia community:** La edición community de n8n no expone la UI de Environment Variables (Settings → Environment Variables). Esa funcionalidad requiere una licencia commercial (pro/enterprise). Por eso el workflow en producción usa un nodo **Config** tipo Set en lugar de `$env.*`.

### Config node (producción)

El workflow activo en `rs-n8n.wilfredocamacho.dev` usa un nodo **Config** (Set, no conectado al flujo) con estos valores:

| Clave | Descripción |
|---|---|
| `trackpal_backend_url` | URL base del backend (ej. `https://trackpal-api.onrender.com`) |
| `trackpal_n8n_api_key` | Mismo valor que `N8N_API_KEY` del backend |
| `evolution_api_url` | URL base de Evolution API (ej. `https://rs-evoapi.wilfredocamacho.dev`) |
| `evolution_api_key` | API key de Evolution API |
| `default_instance` | Nombre de instancia Evolution API por defecto |

Los nodos HTTP (`Console call`, `Evolution API Send`) referencian estos valores con `$('Config').first().json.*` en lugar de `$env.*`.

### Pasos para instancia nueva (community edition)

1. Importar el JSON (`n8n/Trackpal WhatsApp Bot.json`) en n8n.
2. Crear un nodo **Set** llamado **Config** (no conectado a ningún edge) con los pares clave-valor de la tabla anterior.
3. En los nodos `Console call` y `Evolution API Send`, reemplazar `{{$env.TRACKPAL_*}}` con `{{$('Config').first().json.*}}`.
4. Configurar el webhook de Evolution API para apuntar a:
   ```
   https://rs-n8n.wilfredocamacho.dev/webhook/trackpal-whatsapp-bot
   ```
5. Activar el workflow.

> **Alternativa (licencia commercial):** Si tenés una licencia pro/enterprise de n8n, podés usar Settings → Environment Variables y mantener las `$env.*` expressions sin modificar el JSON.

---

## ### Render Blueprint (render.yaml)

El `render.yaml` en la raíz también fue actualizado con el seed en el start command.

## Post-deploy checklist

- [ ] Backend responde en `https://trackpal-api.onrender.com/health` → `{"status":"ok"}`
- [ ] Login funciona: `POST /api/v1/auth/login` con credenciales del Master
- [ ] Frontend carga y redirige a `/login`
- [ ] Login en frontend redirige a `/master/dashboard`
- [ ] List tenants funciona
- [ ] ngrok ya no es necesario (la URL de Render es fija)
- [ ] n8n workflow apunta a la URL de Render
- [ ] Seed del Master ejecutado en producción

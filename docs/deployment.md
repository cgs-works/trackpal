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
   - **Build Command**: `pip install uv && uv sync --directory backend`
   - **Start Command**: `uv run --directory backend alembic upgrade head && uv run --directory backend python scripts/seed.py && uv run --directory backend uvicorn app.main:app --host 0.0.0.0 --port $PORT`
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

### Post-deploy

Render ejecuta automáticamente:
1. `uv sync --directory backend` (instalar dependencias)
2. `uv run --directory backend alembic upgrade head` (migraciones)
3. `uv run --directory backend python scripts/seed.py` (seed del Master)
4. `uv run --directory backend uvicorn app.main:app --host 0.0.0.0 --port $PORT` (servidor)
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

Después del deploy:

1. Reemplazar placeholders en el workflow export (`n8n/trackpal-whatsapp-bot.workflow.json`):
   - `YOUR_TRACKPAL_API_URL` → `https://trackpal-api.onrender.com/api/v1`
   - `YOUR_TRACKPAL_API_KEY` → mismo valor que `N8N_API_KEY`
   - `YOUR_EVOLUTION_API_URL` → tu instancia de Evolution API
   - `YOUR_EVOLUTION_API_KEY` → API key de Evolution API

2. Importar el JSON en n8n o editar los nodos manualmente

3. Configurar el webhook de Evolution API para apuntar a:
   ```
   https://rs-n8n.wilfredocamacho.dev/webhook/trackpal-whatsapp-bot
   ```

4. Activar el workflow

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

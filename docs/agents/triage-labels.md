# Triage Labels

Mapeo de roles canónicos a labels de GitHub en este repo.

| Rol canónico | Label en GitHub | Significado |
|---|---|---|
| `needs-triage` | `needs-triage` | El maintainer necesita evaluar el issue |
| `needs-info` | `needs-info` | Esperando que el reportero dé más información |
| `ready-for-agent` | `ready-for-agent` | Completamente especificado, listo para agente AFK |
| `ready-for-human` | `ready-for-human` | Requiere implementación humana |
| `wontfix` | `wontfix` | No será atendido |

> **Nota**: El label `question` existente fue renombrado a `needs-info` para consistencia con la convención de skills.

Cuando una skill menciona un rol (ej. "aplicar el label AFK-ready"), usa el string de label de la columna derecha.

## Otros labels útiles del repo

Estos labels no son parte del triage canónico pero se usan frecuentemente:

| Label | Uso |
|-------|-----|
| `bug` | Tipo de issue: bug |
| `feature` | Tipo de issue: feature |
| `task` | Tipo de issue: tarea técnica |
| `epic` | Tipo de issue: iniciativa grande |
| `documentation` | Mejoras a documentación |
| `blocked` | Issue bloqueado por dependencia |
| `in-progress` | Trabajo en progreso |
| `review` | En revisión |
| `p0`–`p3` | Prioridad |
| `backend`, `frontend`, `n8n`, `infra`, `docs`, `testing`, `devops`, `security`, `design` | Área del sistema |

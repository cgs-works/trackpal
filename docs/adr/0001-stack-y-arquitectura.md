# Stack y arquitectura inicial de Trackpal

Decidimos usar Python FastAPI + SQLAlchemy + UV para el backend,
Vue 3 + Vite para el frontend, y Supabase PostgreSQL como base de
datos. El proyecto se organiza como monorepo con las carpetas
`backend/` y `frontend/`.

## Consideraciones

- FastAPI ofrece tipado fuerte con Pydantic, async nativo, y buena
  integración con SQLAlchemy para PostgreSQL.
- UV es el gestor de proyectos Python moderno (rápido, con soporte
  de dependencias y entornos virtuales).
- Vue 3 con Composition API + Vite es un stack frontend moderno y
  liviano, compatible con el ecosistema de Supabase.
- Monorepo simplifica el desarrollo inicial y el CI; si el proyecto
  crece, separar repos es trivial.

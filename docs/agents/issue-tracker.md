# Issue tracker: GitHub

Issues para este repo viven en GitHub Issues. Usa el CLI `gh` para todas las operaciones.

## Conventions

- **Create**: `gh issue create --title "..." --body "..."`. Usa heredoc para cuerpos multiline.
- **Read**: `gh issue view <number> --comments`, filtra con `jq` y obtiene labels.
- **List**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` con filtros `--label` y `--state`.
- **Comment**: `gh issue comment <number> --body "..."`
- **Labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infiere el repo desde `git remote -v` — `gh` lo hace automáticamente dentro de un clone.

## Pull requests as a triage surface

**PRs as a request surface: no.**

Los PRs externos no se procesan como issues. Solo se gestionan PRs internos del equipo.

## When a skill says "publish to the issue tracker"

Crea un GitHub issue usando el template apropiado (`bug-report`, `feature-request`, `epic`, `task`).

## When a skill says "fetch the relevant ticket"

Ejecuta `gh issue view <number> --comments`.

## Issue templates

El repo tiene 4 templates configurados en `.github/ISSUE_TEMPLATE/`:

| Template | Labels automáticas | Uso |
|----------|-------------------|-----|
| `bug-report.yml` | `bug`, `p2` | Bugs reproducibles |
| `feature-request.yml` | `feature`, `p2` | Nuevas features o mejoras |
| `epic.yml` | `epic` | Iniciativas grandes compuestas por múltiples issues |
| `task.yml` | `task`, `p2` | Trabajo técnico: refactors, upgrades, tooling, docs, tests |

## Area labels

Los templates aplican un label de área (`backend`, `frontend`, `n8n`, `infra`, `docs`, `testing`, `devops`, `security`, `design`) según el componente afectado.

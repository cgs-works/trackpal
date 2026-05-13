# Phase 5: Profile + Dashboard API

**Complexity:** S
**Dependencies:** Phase 3

## Objective
Create endpoints for users to manage their own profiles and fetch dashboard data.

## Preconditions
- JWT auth working.

## Tasks
1. Context: `backend/app/api/v1/me.py` and `backend/app/api/v1/dashboard.py`.
2. Implement Profile (`/api/v1/me/`):
   - `GET /`: Returns joined User + Profile based on `current_user.role`.
   - `PUT /`: Updates profile details.
   - `PUT /password`: Updates password (verifies old password first).
3. Implement Dashboard (`/api/v1/dashboard/`):
   - `GET /`: Role-aware endpoint. For Tenant, returns simple "under construction" stats + profile info. For Master, returns counts (total, active, inactive tenants).

## Verification
- Commands:
  - `cd backend && uv run pytest tests/test_profile.py`
- Expected results:
  - Both Master and Tenant can fetch/update their profiles successfully.
  - Dashboard endpoint returns appropriate data based on token role.

## Exit Criteria
- Endpoints allow basic profile management and initial dashboard data loading.

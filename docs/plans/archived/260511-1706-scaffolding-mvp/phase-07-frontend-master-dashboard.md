# Phase 7: Frontend: Master Dashboard

**Complexity:** M
**Dependencies:** Phase 4, Phase 6

## Objective
Create the interface for Masters to view, create, edit, deactivate, and delete Tenants.

## Preconditions
- Authentication configured in frontend.
- Backend Tenant CRUD endpoints active.

## Tasks
1. Context: `frontend/src/views/master/MasterDashboard.vue` and components.
2. Implement UI layout:
   - Summary metrics (total tenants, active, inactive).
3. Implement Tenant Table:
   - Fetch from `GET /api/v1/tenants/`.
   - Columns: Full Name, Email, Phone, Evolution Instance, Status.
   - Action buttons: Edit, Deactivate/Activate, Delete.
4. Implement Modals/Forms:
   - Form for creating a new tenant (requires username/password + profile data).
   - Form for editing an existing tenant (profile data).
5. Integrate Actions:
   - Wire action buttons to API endpoints. Ensure Delete is disabled or prompts validation if tenant is active.

## Verification
- Commands:
  - Local testing via browser at `/master/dashboard`.
- Expected results:
  - Table loads with tenants.
  - Create/Edit forms correctly send data to API and update table.

## Exit Criteria
- Complete UI for managing tenants is fully functional.

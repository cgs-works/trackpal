# WhatsApp Link Specification

## Purpose

Provide a backend API that allows Starter and Pro tenant administrators to manage their WhatsApp instance connection lifecycle — checking status, initiating pairing (via code or QR), and disconnecting — without master intervention. The API proxies requests to the Evolution Go API via `EvolutionClient`, enforcing tenant authorization and input validation.

## Requirements

### Requirement: Status Endpoint

The system MUST expose `GET /api/v1/tenant/whatsapp-link/status` that returns the current WhatsApp connection status for the requesting tenant's Evolution instance.

The response body MUST conform to `{ connected: bool, phone: str | null, instance_name: str }`.

- `connected` MUST be `true` when the Evolution instance reports both `connected: true` and `loggedIn: true`; `false` otherwise.
- `phone` MUST be the tenant's `whatsapp_phone` value (may be `null`).
- `instance_name` MUST be the tenant's `evolution_instance_name`.

#### Scenario: Connected instance

- GIVEN a tenant with a configured and connected Evolution instance
- WHEN the tenant calls `GET /api/v1/tenant/whatsapp-link/status`
- THEN the response status MUST be 200
- AND the response body MUST include `connected: true`, the tenant's phone number, and the instance name

#### Scenario: Disconnected instance

- GIVEN a tenant with a configured but disconnected Evolution instance
- WHEN the tenant calls `GET /api/v1/tenant/whatsapp-link/status`
- THEN the response status MUST be 200
- AND the response body MUST include `connected: false`, the tenant's phone number (or `null`), and the instance name

#### Scenario: Missing instance configuration

- GIVEN a tenant without `evolution_instance_name` or `evolution_instance_token` set
- WHEN the tenant calls `GET /api/v1/tenant/whatsapp-link/status`
- THEN the response status MUST be 400
- AND the error MUST use a `UserFacingError` code with an i18n key

---

### Requirement: Pair Endpoint

The system MUST expose `POST /api/v1/tenant/whatsapp-link/pair` that requests an 8-digit pairing code from Evolution Go for the tenant's instance.

The request body MUST be empty (`{}`). The phone number MUST be sourced from `tenant.whatsapp_phone` — the API MUST NOT accept phone input from the client.

The response body MUST conform to `{ code: str }` where `code` is the 8-digit pairing code.

#### Scenario: Successful pairing code request

- GIVEN a tenant with `whatsapp_phone` set, instance configured, and instance not currently connected
- WHEN the tenant calls `POST /api/v1/tenant/whatsapp-link/pair`
- THEN the response status MUST be 200
- AND the response body MUST include a `code` field containing the 8-digit pairing code

#### Scenario: Already connected

- GIVEN a tenant whose Evolution instance is already connected (`connected: true, loggedIn: true`)
- WHEN the tenant calls `POST /api/v1/tenant/whatsapp-link/pair`
- THEN the response status MUST be 409
- AND the error MUST use a `UserFacingError` code with an i18n key indicating the instance is already connected

#### Scenario: No phone configured

- GIVEN a tenant with `whatsapp_phone` set to `null`
- WHEN the tenant calls `POST /api/v1/tenant/whatsapp-link/pair`
- THEN the response status MUST be 400
- AND the error MUST use a `UserFacingError` code with an i18n key indicating a phone number is required

---

### Requirement: QR Code Endpoint

The system MUST expose `GET /api/v1/tenant/whatsapp-link/qr` that returns a QR code image for WhatsApp Web linking.

The response body MUST conform to `{ qrcode: str }` where `qrcode` is a base64-encoded PNG image.

#### Scenario: Successful QR code retrieval

- GIVEN a tenant with instance configured and instance not currently connected
- WHEN the tenant calls `GET /api/v1/tenant/whatsapp-link/qr`
- THEN the response status MUST be 200
- AND the response body MUST include a `qrcode` field containing a base64-encoded PNG string

#### Scenario: Already connected

- GIVEN a tenant whose Evolution instance is already connected
- WHEN the tenant calls `GET /api/v1/tenant/whatsapp-link/qr`
- THEN the response status MUST be 409
- AND the error MUST use a `UserFacingError` code with an i18n key indicating the instance is already connected

#### Scenario: No phone configured

- GIVEN a tenant with `whatsapp_phone` set to `null`
- WHEN the tenant calls `GET /api/v1/tenant/whatsapp-link/qr`
- THEN the response status MUST be 400
- AND the error MUST use a `UserFacingError` code with an i18n key indicating a phone number is required

---

### Requirement: Disconnect Endpoint

The system MUST expose `POST /api/v1/tenant/whatsapp-link/disconnect` that logs out the tenant's WhatsApp instance without deleting the Evolution instance.

The endpoint MUST call Evolution's `POST /instance/logout` via `EvolutionClient.logout_instance`.

The Evolution instance MUST be preserved after logout so the tenant can re-link later.

#### Scenario: Successful disconnect

- GIVEN a tenant with a connected Evolution instance
- WHEN the tenant calls `POST /api/v1/tenant/whatsapp-link/disconnect`
- THEN the response status MUST be 200
- AND the Evolution instance MUST be logged out but NOT deleted
- AND subsequent calls to the status endpoint MUST return `connected: false`

#### Scenario: Already disconnected

- GIVEN a tenant whose Evolution instance is already disconnected
- WHEN the tenant calls `POST /api/v1/tenant/whatsapp-link/disconnect`
- THEN the endpoint SHOULD return 200 (idempotent behavior)

---

### Requirement: Authentication and Authorization

All WhatsApp Link endpoints MUST require a valid JWT token and an active tenant context.

The caller MUST be either the tenant admin or a master user acting in a support context for that tenant.

#### Scenario: Valid Starter or Pro tenant JWT

- GIVEN a request with a valid JWT for an active Starter or Pro tenant
- WHEN any WhatsApp Link endpoint is called
- THEN the request MUST proceed to endpoint logic

#### Scenario: Missing or invalid JWT

- GIVEN a request without a JWT or with an expired/invalid JWT
- WHEN any WhatsApp Link endpoint is called
- THEN the response status MUST be 401

#### Scenario: Inactive tenant

- GIVEN a request with a valid JWT for an inactive tenant
- WHEN any WhatsApp Link endpoint is called
- THEN the response status MUST be 401
- AND the error detail MUST indicate the account is deactivated

#### Scenario: Master support context

- GIVEN a master user acting in a support context for a specific tenant
- WHEN any WhatsApp Link endpoint is called
- THEN the request MUST proceed as if the tenant admin called it

---

### Requirement: Instance Configuration Validation

All WhatsApp Link endpoints MUST validate that the tenant has both `evolution_instance_name` and `evolution_instance_token` configured before proxying to Evolution.

#### Scenario: Missing instance name

- GIVEN a tenant without `evolution_instance_name`
- WHEN any WhatsApp Link endpoint is called
- THEN the response status MUST be 400
- AND the error MUST use a `UserFacingError` code with an i18n key

#### Scenario: Missing instance token

- GIVEN a tenant without `evolution_instance_token`
- WHEN any WhatsApp Link endpoint is called
- THEN the response status MUST be 400
- AND the error MUST use a `UserFacingError` code with an i18n key

---

### Requirement: EvolutionClient Methods

`EvolutionClient` MUST expose four new methods for WhatsApp instance management. All methods MUST use the tenant's instance token for authentication against the Evolution Go API.

- `get_instance_status(instance_name: str, instance_token: str)` — returns connection status
- `get_qr_code(instance_name: str, instance_token: str)` — returns base64-encoded QR code PNG
- `pair_instance(instance_name: str, instance_token: str, phone: str)` — returns 8-digit pairing code
- `logout_instance(instance_name: str, instance_token: str)` — logs out the instance

#### Scenario: Successful Evolution API call

- GIVEN valid instance credentials and the Evolution API is available
- WHEN any EvolutionClient WhatsApp method is called
- THEN the method MUST return the expected data from the Evolution API response

#### Scenario: Evolution API downtime

- GIVEN the Evolution API is unreachable or returns a 5xx error
- WHEN any EvolutionClient WhatsApp method is called
- THEN the method MUST raise an error that results in a user-facing "Service unavailable" message with an i18n key

#### Scenario: Invalid instance token

- GIVEN an invalid or expired instance token
- WHEN any EvolutionClient WhatsApp method is called
- THEN the method MUST raise an error that results in a clear user-facing error message suggesting the user contact support

---

### Requirement: Error Response Format

All error responses from WhatsApp Link endpoints MUST use `UserFacingError` codes with i18n keys.

Error messages MUST be available in both English and Spanish catalogs.

#### Scenario: i18n error keys exist in both catalogs

- GIVEN any error condition producible by the WhatsApp Link endpoints
- WHEN the error is raised
- THEN the error code MUST resolve to a translation in both `_catalog_en.py` and `_catalog_es.py`

---

### Requirement: No Database Schema Changes

The WhatsApp Link feature MUST NOT require any database migrations or schema changes. All required tenant fields (`evolution_instance_name`, `evolution_instance_token`, `whatsapp_phone`) already exist in the tenant model.

#### Scenario: Feature deployment

- GIVEN the WhatsApp Link feature is deployed
- THEN no Alembic migration files MUST be generated or required for this feature
- AND the feature MUST operate using only existing tenant model fields

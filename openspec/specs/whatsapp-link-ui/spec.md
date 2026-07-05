# WhatsApp Link UI Specification

## Purpose

Provide a frontend settings section that enables Starter and Pro tenant administrators to view their WhatsApp connection status, initiate pairing (via code or QR), and disconnect — directly from the admin panel without master intervention. The section handles connection polling and displays all text via i18n.

## Requirements

### Requirement: Settings Section Visibility

The "WhatsApp" section MUST appear in the tenant Settings page for active Starter and Pro tenant admins, and for a master acting in a support context for the tenant.

#### Scenario: Pro tenant sees WhatsApp section

- GIVEN a tenant with `plan === "pro"`
- WHEN the tenant admin navigates to Settings
- THEN the "WhatsApp" section MUST be visible

#### Scenario: Starter tenant sees WhatsApp section

- GIVEN a tenant with `plan === "starter"`
- WHEN the tenant admin navigates to Settings
- THEN the "WhatsApp" section MUST be visible

#### Scenario: Master support context sees WhatsApp section

- GIVEN a master user acting in support context for any tenant (regardless of plan)
- WHEN the master navigates to the tenant's Settings
- THEN the "WhatsApp" section MUST be visible

---

### Requirement: Status Display

When the WhatsApp section is visible, it MUST display the tenant's phone number, a connection status badge, and contextual action buttons.

The status badge MUST show one of: **Connected**, **Disconnected**, or **Connecting**.

#### Scenario: Connected state display

- GIVEN the tenant's WhatsApp instance is connected
- WHEN the WhatsApp section is rendered
- THEN it MUST show the phone number from the status API response
- AND the status badge MUST indicate "Connected"
- AND a "Disconnect" button MUST be available

#### Scenario: Disconnected state display

- GIVEN the tenant's WhatsApp instance is disconnected
- WHEN the WhatsApp section is rendered
- THEN it MUST show the phone number (or indicate none configured)
- AND the status badge MUST indicate "Disconnected"
- AND pairing action buttons MUST be available

#### Scenario: Connecting state display

- GIVEN a pairing or QR flow has been initiated and polling is active
- WHEN the WhatsApp section is rendered
- THEN the status badge MUST indicate "Connecting"

---

### Requirement: Phone Number Block

If the tenant has no `whatsapp_phone` configured (`null`), the WhatsApp section MUST display a block message instead of the pairing UI.

The block message MUST be displayed via an i18n key (e.g., "Configure your phone number first" / "Configure su número de teléfono primero").

#### Scenario: No phone configured

- GIVEN the tenant's `whatsapp_phone` is `null` (status API returns `phone: null`)
- WHEN the WhatsApp section is rendered
- THEN the pairing UI (tabs, buttons) MUST NOT be shown
- AND a block message MUST be displayed using the appropriate i18n key

---

### Requirement: Pairing Code Tab

The section MUST provide a "Pairing Code" tab that requests an 8-digit pairing code from the backend and displays it with user instructions.

The phone number MUST NOT be editable — it is auto-filled from `tenant.whatsapp_phone` via the status API.

#### Scenario: Requesting a pairing code

- GIVEN the tenant's instance is disconnected and phone is configured
- WHEN the user activates the "Pairing Code" tab and initiates pairing
- THEN the UI MUST call `POST /api/v1/tenant/whatsapp-link/pair`
- AND display the returned 8-digit code prominently
- AND show instructions for entering the code in WhatsApp (via i18n)

#### Scenario: Already connected rejection

- GIVEN the backend returns 409 (already connected)
- WHEN the user attempts to request a pairing code
- THEN the UI MUST display a translated error message indicating the instance is already connected

---

### Requirement: QR Code Tab

The section MUST provide a "QR Code" tab that displays a QR code image for WhatsApp Web linking with auto-refresh on expiry.

#### Scenario: Displaying QR code

- GIVEN the tenant's instance is disconnected
- WHEN the user activates the "QR Code" tab
- THEN the UI MUST call `GET /api/v1/tenant/whatsapp-link/qr`
- AND render the returned base64 PNG as a visible QR code image
- AND show instructions for scanning the code in WhatsApp (via i18n)

#### Scenario: QR code auto-refresh

- GIVEN a QR code is displayed and it expires (approximately 40-second window)
- WHEN the expiry is detected (e.g., via timer or failed poll)
- THEN the UI MUST automatically request a new QR code from the backend
- AND replace the expired QR code with the fresh one

---

### Requirement: Connection Polling

After the user initiates a pairing code or QR code flow, the UI MUST poll `GET /api/v1/tenant/whatsapp-link/status` every 5 seconds to detect successful connection.

Polling MUST stop when the status returns `connected: true` OR after a 60-second timeout.

#### Scenario: Polling detects successful connection

- GIVEN pairing or QR flow has been initiated
- WHEN the status endpoint returns `connected: true` during polling
- THEN polling MUST stop
- AND the UI MUST transition to the "Connected" state

#### Scenario: Polling timeout

- GIVEN pairing or QR flow has been initiated
- WHEN 60 seconds elapse without `connected: true`
- THEN polling MUST stop
- AND the UI MUST display a timeout message (via i18n) and allow the user to retry

#### Scenario: Polling interval

- GIVEN polling is active
- THEN status requests MUST be spaced approximately 5 seconds apart

---

### Requirement: Success Toast

When a successful connection is detected (polling returns `connected: true`), the UI MUST display a Sonner toast notification confirming the link.

The toast text MUST use an i18n key (e.g., "¡WhatsApp vinculado exitosamente!" / "WhatsApp linked successfully!").

#### Scenario: Toast on successful connection

- GIVEN a pairing or QR flow is in progress
- WHEN the status transitions to `connected: true`
- THEN a Sonner toast MUST be displayed with the translated success message

---

### Requirement: Disconnect Flow

The section MUST provide a "Disconnect" button when the instance is connected.

Clicking "Disconnect" MUST call `POST /api/v1/tenant/whatsapp-link/disconnect` and update the UI to reflect the disconnected state.

#### Scenario: Successful disconnect

- GIVEN the tenant's instance is connected
- WHEN the user clicks "Disconnect"
- THEN the UI MUST call `POST /api/v1/tenant/whatsapp-link/disconnect`
- AND the status badge MUST update to "Disconnected"
- AND the pairing UI MUST become available again

---

### Requirement: Error Handling

All API errors MUST be displayed as translated error messages in the UI.

When the Evolution API is unavailable (backend returns a service unavailable error), the section MUST show a "Service unavailable" message (via i18n) with an option to retry.

#### Scenario: API error display

- GIVEN any WhatsApp Link API call returns an error
- WHEN the error response is received
- THEN the UI MUST display the translated error message from the error response

#### Scenario: Service unavailable

- GIVEN the backend returns a service unavailable error (Evolution API down)
- WHEN the user interacts with the WhatsApp section
- THEN the UI MUST display a "Service unavailable" message via i18n
- AND provide a retry option

---

### Requirement: Internationalization

All user-visible text in the WhatsApp section MUST use the `t()` translation function with i18n keys. No strings MUST be hardcoded in the component.

Both Spanish (ES) and English (EN) translations MUST be provided for all keys.

#### Scenario: All text is translated

- GIVEN the WhatsApp section is rendered in any supported locale
- THEN every visible text element MUST be rendered via `t()` with an i18n key
- AND no hardcoded language strings MUST appear in the component source

#### Scenario: Spanish locale

- GIVEN the user's locale is `es`
- WHEN the WhatsApp section is rendered
- THEN all text MUST appear in Spanish

#### Scenario: English locale

- GIVEN the user's locale is `en`
- WHEN the WhatsApp section is rendered
- THEN all text MUST appear in English

---

### Requirement: API Service Layer

A dedicated API service file MUST exist (e.g., `whatsapp-link-api.ts`) that encapsulates all WhatsApp Link API calls with typed request/response interfaces.

#### Scenario: Typed API functions exist

- GIVEN a developer needs to call WhatsApp Link endpoints
- THEN the following typed functions MUST be available in the service file:
  - `getWhatsAppLinkStatus()` → `{ connected: boolean, phone: string | null, instance_name: string }`
  - `requestPairingCode()` → `{ code: string }`
  - `getQRCode()` → `{ qrcode: string }`
  - `disconnectWhatsApp()` → success response

# PRD: WhatsApp Master Console

## Problem Statement

The Master needs to manage Tenants from WhatsApp with the same confidence and completeness as the Master dashboard. The current WhatsApp workflow cannot reliably support multi-step actions because conversational state is not available across webhook executions. When the Master starts creating a Tenant and sends the full name, the flow can lose context and return to the main menu instead of continuing to the next creation step.

The current workflow also puts too much product behavior in n8n. That makes Tenant CRUD harder to test, harder to version, and fragile as the conversational interface grows. The Master needs a dashboard-like WhatsApp console where menu navigation, Tenant selection, form collection, validation, confirmation, and lifecycle rules are consistent with Trackpal's backend domain rules.

## Solution

Build a WhatsApp Master Console where n8n acts only as the WhatsApp transport and the backend owns the conversation logic. n8n receives messages from Evolution API, normalizes the inbound message, calls a backend console entrypoint protected by the n8n API key, and sends the backend's reply back through Evolution API.

The backend stores ephemeral conversational state in Redis, keyed by the Master's phone number. Redis keeps the current flow, step, selected Tenant, temporary form data, and any numbered Tenant selection map needed to interpret follow-up messages. The state expires automatically and can be cleared by the Master with menu or cancel commands.

The console supports complete Tenant CRUD from WhatsApp through categorized menus:

1. Ver tenants
2. Crear tenant
3. Desactivar tenant
4. Eliminar tenant
5. Ayuda
0. Cancelar / menú

The Master can list Tenants, select a Tenant by number, view details, edit Tenant fields, activate or deactivate a Tenant, create a new Tenant through a guided flow, and delete only inactive Tenants after explicit confirmation.

## User Stories

1. As the Master, I want to open a WhatsApp menu, so that I can manage Trackpal without using the browser dashboard.
2. As the Master, I want the WhatsApp menu to show clear categories, so that I can choose between viewing, creating, deactivating, deleting, or getting help.
3. As the Master, I want to type `0`, `menu`, `menú`, or `cancelar`, so that I can abandon the current flow and return to the main menu.
4. As the Master, I want my current WhatsApp flow to continue across messages, so that a multi-step action does not reset after each webhook execution.
5. As the Master, I want inactive or expired conversational sessions to reset safely, so that old partial actions do not accidentally continue later.
6. As the Master, I want to list Tenants from WhatsApp, so that I can inspect the current Tenant base quickly.
7. As the Master, I want the Tenant list to use numbered options, so that I can select a Tenant without typing UUIDs or long identifiers.
8. As the Master, I want the system to remember the numbered Tenant list for my session, so that replying with `1` selects the Tenant that was shown as option 1.
9. As the Master, I want to see each Tenant's relevant status in the list, so that I can distinguish active and inactive Tenants before taking action.
10. As the Master, I want to select a Tenant and see its details, so that I can confirm I am editing or changing the correct Tenant.
11. As the Master, I want the selected Tenant detail screen to show available actions, so that I can edit, activate, deactivate, or return without guessing commands.
12. As the Master, I want to edit a Tenant's full name from WhatsApp, so that I can correct display information without opening the dashboard.
13. As the Master, I want to edit a Tenant's email from WhatsApp, so that contact data stays current.
14. As the Master, I want to edit a Tenant's phone from WhatsApp, so that Tenant identification and contact information stay current.
15. As the Master, I want to edit a Tenant's Evolution Instance name from WhatsApp, so that WhatsApp integration metadata can be corrected.
16. As the Master, I want edited Tenant fields to be validated by the backend, so that invalid or conflicting data is rejected consistently.
17. As the Master, I want validation errors to explain what failed and what to send next, so that I can recover without restarting the full flow.
18. As the Master, I want to create a Tenant through a guided WhatsApp flow, so that I can onboard a Tenant from my phone.
19. As the Master, I want the create flow to ask for full name first, so that the Tenant has the required profile identity.
20. As the Master, I want the create flow to support optional email, so that I can skip email when it is not available.
21. As the Master, I want the create flow to support optional phone, so that I can skip phone when it is not available.
22. As the Master, I want the create flow to ask for username, so that the Tenant can log into Trackpal.
23. As the Master, I want the create flow to ask for Evolution Instance name, so that the Tenant can be linked to WhatsApp infrastructure when applicable.
24. As the Master, I want the create flow to let me choose between automatic and manual password, so that I can balance convenience and control.
25. As the Master, I want automatically generated passwords to be shown only as part of the creation result, so that I understand this is sensitive information.
26. As the Master, I want manual password entry to be treated as sensitive, so that the interface warns me about sending credentials in WhatsApp.
27. As the Master, I want to review a creation summary before committing, so that I can catch mistakes before the Tenant is created.
28. As the Master, I want creation to happen only after confirmation, so that partial data collection does not create incomplete Tenants.
29. As the Master, I want the original creation bug fixed, so that after sending the full name the next response asks for the next field instead of returning to the main menu.
30. As the Master, I want duplicate username or duplicate phone errors to be handled in the same flow, so that I can correct the field and continue.
31. As the Master, I want to deactivate a Tenant from WhatsApp, so that I can suspend access quickly.
32. As the Master, I want deactivation to require confirmation, so that I do not deactivate a Tenant accidentally.
33. As the Master, I want deactivation to follow the existing Tenant lifecycle rules, so that the Tenant cannot log in or be identified after deactivation.
34. As the Master, I want to reactivate an inactive Tenant from the selected Tenant detail screen, so that I can restore access when needed.
35. As the Master, I want to delete a Tenant from WhatsApp only when the Tenant is inactive, so that destructive lifecycle rules match the backend domain model.
36. As the Master, I want deletion of an active Tenant to be blocked with an explanation, so that I know I must deactivate first.
37. As the Master, I want deletion to require an explicit textual confirmation such as `CONFIRMAR`, so that accidental numeric replies cannot delete a Tenant.
38. As the Master, I want destructive actions to show the Tenant name and status before confirmation, so that I know exactly what will be changed.
39. As the Master, I want help text to explain available commands, so that I can recover when I forget the menu options.
40. As the Master, I want unrecognized input to return a helpful message, so that I understand whether to choose an option, continue the current step, or cancel.
41. As a non-Master user, I should not be able to use the WhatsApp Master Console, so that Tenant management remains restricted to the Master.
42. As Trackpal, I want n8n requests to the backend console to require the n8n API key, so that the console cannot be called publicly without authorization.
43. As Trackpal, I want the backend to identify the Master by phone before processing console commands, so that commands are tied to a known Master identity.
44. As Trackpal, I want n8n to avoid direct Tenant CRUD calls, so that product rules stay in the backend and are easier to test.
45. As Trackpal, I want the WhatsApp reply contract to be simple, so that n8n can send the returned message without duplicating business logic.
46. As Trackpal, I want Redis session data to be ephemeral, so that conversational state does not become permanent business data.
47. As Trackpal, I want session expiration to be predictable, so that stale flows do not create or modify Tenants after a long delay.
48. As Trackpal, I want automated tests to avoid sending real WhatsApp messages, so that verification is safe and repeatable.

## Modules

- **WhatsApp Master Console Endpoint** — Single backend conversation entrypoint for n8n. Interface: accepts a normalized phone, message, and optional Evolution Instance context from n8n; validates the n8n API key; identifies the Master; returns the WhatsApp reply text.
- **Redis Conversation Session** — Ephemeral session store for the console. Interface: get current session by Master phone, update current flow and step, store selected Tenant context and temporary input, store numbered Tenant selection maps, clear session, and expire sessions through TTL.
- **Tenant CRUD Conversation Flows** — Backend-owned flow logic for Tenant management through WhatsApp. Interface: interpret current session plus inbound message, transition to the next step, call existing Tenant lifecycle operations, and produce the next reply.
- **n8n Transport Workflow** — WhatsApp transport layer. Interface: parse inbound Evolution API payload, normalize message data, call the backend console endpoint with the n8n API key, and send the returned reply through Evolution API.

## Implementation Decisions

- Conversational state lives in Redis, not PostgreSQL.
- Redis state is ephemeral and keyed by Master phone number.
- Session TTL is 30 minutes by default and may be made configurable.
- `0`, `menu`, `menú`, and `cancelar` clear the current session and return the Master to the main menu.
- The backend owns conversation state transitions, validation, Tenant selection, and CRUD decisions.
- n8n is reduced to WhatsApp transport and orchestration: receive, normalize, call backend, send reply.
- n8n must not own the multi-step menu state or perform direct Tenant CRUD for the Master Console.
- The main menu is categorized as: Ver tenants, Crear tenant, Desactivar tenant, Eliminar tenant, Ayuda, and Cancelar / menú.
- Tenant selection uses numbered lists. Redis stores the mapping from displayed number to Tenant identity for the active Master session.
- Selecting a Tenant opens a detail and actions screen for editing and lifecycle actions.
- The create flow collects: full name, optional email, optional phone, username, Evolution Instance name, password mode, password value when manual, confirmation, then creation.
- Destructive actions require explicit textual confirmation such as `CONFIRMAR`.
- Active Tenants cannot be deleted from WhatsApp. The Master must deactivate them first.
- Tenant lifecycle behavior must match the existing backend rules for creation, activation, deactivation, and deletion.
- Non-Master users must not access Master console actions from WhatsApp.
- The backend response to n8n should remain simple enough for n8n to send without interpreting product behavior.

## Testing Decisions

- Good tests should verify external behavior: given a Master phone, a message, and an existing session state, the system returns the expected reply and session transition.
- Tests should avoid implementation details of internal helper functions unless those helpers are intentionally exposed as module interfaces.
- The WhatsApp Master Console Endpoint must be tested for API-key authorization, Master identification, non-Master rejection, expected request shape, and expected response shape.
- Redis Conversation Session behavior must be tested for session creation, update, clearing, TTL behavior, and cancel/menu reset behavior.
- Tenant CRUD Conversation Flows must be tested from the WhatsApp user's perspective: list, select, view, edit, create, deactivate, reactivate, and delete inactive Tenants.
- The original regression must be covered: after the Master starts creating a Tenant and sends the full name, the next reply continues the creation flow instead of returning to the main menu.
- Create-flow validation must be tested for required full name, duplicate username, duplicate phone, optional email, optional phone, automatic password, manual password, and confirmation.
- Destructive-flow tests must verify that deactivation and deletion require explicit confirmation and that deletion of an active Tenant is blocked.
- n8n/backend contract tests must verify normalized input, API-key use, and that n8n can send the backend reply without needing to interpret flow state.
- Automated tests must not send real WhatsApp messages through Evolution API.
- Existing async backend test patterns should be reused where possible, with external services disabled or replaced by safe test doubles.

## Out of Scope

- Customer CRUD from WhatsApp.
- Subscription CRUD from WhatsApp.
- Service catalog management from WhatsApp.
- Tenant self-service WhatsApp flows.
- Persisting conversational state in PostgreSQL.
- Reworking the Vue Master dashboard.
- Tenant QR self-service generation.
- Multi-language WhatsApp support.
- Sending real WhatsApp messages in automated tests.
- Building a generalized chatbot or AI assistant.

## Further Notes

This PRD supersedes the prior assumption that n8n data tables should own WhatsApp conversation state for Tenant CRUD. The selected direction is Redis-backed ephemeral session state with backend-owned conversation logic and n8n as transport.

A follow-up Architecture Decision Record is appropriate for the Redis-backed WhatsApp Master Console session decision because it changes the durable integration architecture between n8n, the backend, and conversational state.

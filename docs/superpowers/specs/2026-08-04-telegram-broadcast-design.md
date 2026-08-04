# Telegram Broadcast Design

**Status:** Approved

## Goal

Enable the sole TrackPal Master to publish an immediate, manually confirmed editorial Broadcast to the single official TrackPal Telegram channel. The channel may be public or private. A Broadcast contains formatted text and an ordered collection of optional photos, videos, and documents.

The Master may paste copy drafted by an external LLM, but TrackPal does not call an LLM and never publishes without an explicit Master confirmation.

## Domain Language

- **TrackPal Broadcast Channel**: the official editorial Telegram channel for TrackPal. It is the sole destination for Master-created Broadcasts and may be public or private. It is not a support chat or a tenant channel.
- **Broadcast**: an editorial publication manually confirmed by the Master for the TrackPal Broadcast Channel. It contains formatted text and an ordered sequence of attachments. It is not an automated post or a notification.
- **Broadcast Composer**: the Master-only surface used to review a Broadcast before confirming immediate publication.

The backend and frontend context glossaries record these terms.

## Scope

### Included

- A dedicated Master route, `/master/broadcast`, linked as **Broadcast** from `MasterLayout`.
- A composer for a required Telegram MarkdownV2 message body and a user-ordered collection of attachments.
- Multiple attachments, limited to ten per Broadcast:
  - photos: JPEG, PNG, and WebP;
  - video: MP4;
  - documents: PDF, plain text, CSV, DOCX, XLSX, and PPTX.
- A confirmation dialog before immediate publication.
- Direct server-side delivery to the Telegram Bot API.
- A result screen that reports fully published, partial, or failed delivery.
- Ephemeral Redis-backed idempotency protection.
- Backend, frontend, and documentation coverage.

### Excluded

- LLM provider integration or autonomous publication.
- Scheduled publishing, persistent retries, or queues.
- Publication history, drafts, reuse, or permanent attachment storage.
- Editing or deleting published Telegram messages.
- Multiple selectable channels, incoming Telegram updates, or support-chat behavior.
- Albums or remote rollback when part of a Broadcast was sent.

## Architecture

The browser never contacts Telegram directly. It cannot access a bot token or select a destination.

```text
Master browser
  -> POST /api/v1/broadcasts (multipart + Idempotency-Key)
  -> Broadcast endpoint (Master role)
  -> BroadcastService
       -> Redis idempotency record
       -> TelegramBroadcastClient
            -> Telegram Bot API
```

### Frontend

`MasterLayout` gains a Broadcast navigation item and the new route renders `BroadcastComposer`.

The composer contains:

- a required textarea for MarkdownV2 text;
- concise guidance that external LLM drafts must use Telegram MarkdownV2, rather than ordinary Markdown;
- a multiple-file picker restricted to the allowed file classes;
- a list that shows attachment order and supports removal and reordering;
- local validation before confirmation;
- a confirmation dialog showing the exact text and ordered attachment metadata;
- submission, success, partial-success, and failure states.

The confirmation is a deliberate editorial control, not a password step-up. The submit control is disabled while the request is in progress.

### Backend

A Master-only multipart endpoint accepts the text and uploaded files. It validates the request and delegates all delivery behavior to a deep `BroadcastService` module. Its interface accepts a validated Broadcast and returns a delivery outcome; callers do not need to know Telegram method names, credentials, response shapes, or partial-delivery details.

`TelegramBroadcastClient` is an adapter behind that seam. It owns all `httpx` communication with the Telegram Bot API and maps Telegram-specific failures into safe application results. The adapter is injected or otherwise replaceable in tests; tests must not call Telegram.

Configuration is loaded only on the server:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BROADCAST_CHAT_ID`

`TELEGRAM_BROADCAST_CHAT_ID`, not `https://t.me/trackpal`, is the canonical destination. This keeps delivery stable if the channel becomes private. Before deployment, an operator must create the bot, save its token in the secret store, add it to the channel as an administrator with permission to publish, and configure the channel's stable chat ID.

## Delivery Contract

### Validation

- Text is required and its MarkdownV2 source must contain at most 4,096 Unicode characters.
- At most ten attachments are allowed.
- Each attachment is at most 50 MiB; the aggregate request limit is 500 MiB.
- Every attachment must match an allowed media class and both its filename extension and declared MIME type must agree with that class.
- The service validates local structural limits before contacting Telegram. Telegram remains the authority for MarkdownV2 syntax and remote file acceptance.
- Missing configuration or unavailable Redis rejects the request before any Telegram call.

### Ordering

The body is sent first with Telegram's text-message method. Each attachment is then sent independently, in the exact order selected by the Master, through the appropriate photo, video, or document method. This deliberately does not use Telegram media albums: mixed photo, video, and document collections are consistently ordered and each file has an individual delivery result.

A Broadcast with attachments is therefore a sequence of Telegram channel messages. Telegram cannot make the sequence atomic.

### Results and partial delivery

The delivery outcome includes the status and the indexes of successfully delivered elements, without retaining body text, filenames, or file bytes.

- **published**: the body and every attachment were delivered.
- **partial**: at least one element was delivered and a later element failed. Earlier posts remain in the channel.
- **failed**: no element was delivered.

There are no automatic retries, deletes, or compensating actions. A partial result identifies what reached the channel so the Master can deliberately decide whether to publish a follow-up Broadcast.

### Idempotency

The frontend creates one `Idempotency-Key` when the Master confirms publication. Redis atomically claims a record scoped to the Master user and key before the first Telegram call, then keeps the request fingerprint and minimum delivery outcome for ten minutes.

- A concurrent repeat while the original request is in progress returns a safe `broadcast_in_progress` conflict and never starts a second publication.
- Repeating the same completed key and fingerprint returns the original outcome without publishing again.
- Reusing the key for different input returns a conflict.
- The ephemeral record does not contain the text, filenames, file contents, token, or chat ID.
- Redis unavailability fails closed because the application cannot reliably protect the channel from duplicate publication.

## Error Handling and Security

- The endpoint requires the existing `MasterUser` dependency. Tenant, Client, anonymous, and support-context sessions cannot publish.
- Validation errors, missing setup, malformed Telegram markup, permission failures, remote rate limits, and transport failures produce localized, safe user-facing messages.
- A local validation/setup failure happens before delivery. An external failure after delivery begins is represented as a partial or failed outcome as applicable.
- Logs include only safe operational context: operation name, Master ID, result category, delivered indexes/count, and external error category. They never include tokens, channel IDs, body text, filenames, file bytes, or raw Telegram payloads.
- The frontend receives neither `TELEGRAM_BOT_TOKEN` nor `TELEGRAM_BROADCAST_CHAT_ID`.

## Testing

### Backend

- Adapter tests mock Telegram HTTP responses and assert each outgoing text/photo/video/document request uses the configured channel and correct ordering.
- Service tests cover empty or overlong text, attachment count/size/type validation, full success, first-send failure, later partial failure, and safe Telegram error mapping.
- Endpoint tests cover Master authorization, multipart contract, missing configuration, Redis failure, and idempotency outcomes.
- Tests assert secrets and content are absent from stored idempotency records and logs.

### Frontend

- Route and navigation visibility are restricted to the Master.
- Composer tests cover text/file validation, attachment removal and reordering, confirmation being mandatory, disabled duplicate submission, expected multipart request construction, and each outcome state.
- Tests verify no Telegram credential or channel configuration appears in browser-visible data.

## Documentation

The implementation updates the API-layer and frontend-architecture docs with the new Master route and multipart endpoint. It adds `docs/how-to/configure-telegram-broadcast.md`, an operational runbook for the bot token, private-channel chat ID, administrator permission, and safe rotation. It also updates the backend and frontend context glossaries with the approved domain language.

### How-to: publish a Telegram Broadcast

Create `docs/how-to/publish-telegram-broadcast.md` as an operator-focused Diátaxis how-to, then add it to `docs/SUMMARY.md`. It must explain how a Master:

1. verifies the channel configuration and bot publishing permission before composing;
2. prepares MarkdownV2 text, including the distinction from ordinary Markdown and a small escaping example;
3. chooses, orders, and validates up to ten supported photos, videos, or documents;
4. reviews and explicitly confirms immediate publication;
5. reads the published, partial, and failed outcomes; and
6. safely responds to a partial Broadcast without assuming TrackPal can undo already delivered channel posts.

The how-to must state its prerequisites, avoid exposing actual credentials or channel IDs, and link to `docs/how-to/configure-telegram-broadcast.md`. It is procedural documentation only: it does not document LLM prompts, scheduling, history, or unsupported media types.

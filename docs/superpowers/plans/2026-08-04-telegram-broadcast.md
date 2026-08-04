# Telegram Broadcast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the authenticated Master publish one immediately confirmed, MarkdownV2-formatted Telegram Broadcast with ordered photos, videos, and documents to TrackPal's one configured channel.

**Architecture:** The browser submits multipart data only to `POST /api/v1/broadcasts`; the backend validates the input, claims an ephemeral Redis idempotency record, and delegates Telegram delivery to a `TelegramBroadcastClient` that wraps `python-telegram-bot`. A Master-only React composer owns the local form, confirmation dialog, attachment order, and rendering of the resulting `published`, `partial`, or `failed` outcome.

**Tech Stack:** Python 3.12, FastAPI 0.136, Pydantic v2, `python-telegram-bot` 22.5, Redis HA, `python-multipart`, pytest + pytest-asyncio, React 19, TypeScript strict mode, TanStack Router, Axios, Tailwind CSS v4, Base UI/shadcn primitives, Vitest, Testing Library.

## Global Constraints

- The sole target is the server-configured TrackPal Broadcast Channel. The browser must never receive `TELEGRAM_BOT_TOKEN` or `TELEGRAM_BROADCAST_CHAT_ID` and cannot select a channel.
- Only a Master outside tenant support context may call `POST /api/v1/broadcasts`; tenant, client, anonymous, and Master sessions carrying `active_tenant_id` must be rejected before publication.
- `body` is required Telegram MarkdownV2 source with at most 4,096 Unicode code points.
- A Broadcast has at most 10 attachments and a 500 MiB aggregate limit. Each attachment is at most 50 MiB and must match one allowed extension/MIME pair: JPEG, PNG, WebP, MP4, PDF, TXT, CSV, DOCX, XLSX, or PPTX.
- Send the text first, then each attachment independently and in selected order. Do not create albums, schedule messages, persist uploads, retry automatically, delete remote posts, or create publication history.
- The result reports `published`, `partial`, or `failed` and only delivered attachment indexes. Do not store message text, filenames, bytes, bot token, or channel ID in Redis or logs.
- A frontend-created `Idempotency-Key` is scoped to the Master and an input fingerprint in Redis for exactly 10 minutes. Concurrent identical requests return `broadcast_in_progress`; completed identical requests return the cached outcome; a changed fingerprint for the same key returns a conflict. Redis absence or failure must fail closed before Telegram is called.
- All new visible UI copy comes from the backend i18n catalog in English and Spanish. Do not edit `frontend/src/routeTree.gen.ts` manually; `npm run build` regenerates it.
- Preserve the unrelated local change already present in `backend/app/core/i18n/catalogs_en_general.py`; do not stage, revert, or fold it into this feature.

---

## File Structure

### Backend delivery and endpoint

| Path | Responsibility |
|---|---|
| `backend/app/services/telegram_broadcast.py` | Domain request/attachment/outcome types, allow-list validation, `python-telegram-bot` adapter, and safe Telegram failure classification. |
| `backend/app/services/broadcast_service.py` | Small application interface that computes idempotency state, calls a publisher, and returns cached or live outcomes. |
| `backend/app/api/v1/endpoints/broadcasts.py` | Global-Master-only multipart boundary; converts `UploadFile` values into validated attachments and maps stable error codes to HTTP responses. |
| `backend/app/schemas/broadcast.py` | Pydantic response model for the browser-facing outcome. |
| `backend/app/core/config.py` | Server-only bot token and channel ID settings. |
| `backend/app/api/v1/router.py` | Includes the broadcasts router under `/api/v1`. |
| `backend/pyproject.toml`, `backend/uv.lock` | Adds `python-telegram-bot` and FastAPI's multipart parser dependencies. |
| `backend/.env.example` | Documents the two Telegram variables with empty example values. |
| `backend/app/core/i18n/catalogs_en_frontend.py`, `backend/app/core/i18n/catalogs_es_frontend.py` | Adds Master Broadcast UI and safe error/result strings. |
| `backend/tests/test_telegram_broadcast.py` | Unit tests for validation, ordered Bot API requests, and safe failure mapping. |
| `backend/tests/test_broadcast_service.py` | Unit tests for the ten-minute Redis claim/cache contract. |
| `backend/tests/test_broadcasts_api.py` | ASGI tests for Master authorization, multipart input, HTTP error mapping, and outcome serialization. |

### Frontend composer

| Path | Responsibility |
|---|---|
| `frontend/src/routes/master/broadcast.tsx` | File-based route that renders the composer. |
| `frontend/src/features/master/layout/master-layout.tsx` | Adds the Master-only Broadcast navigation destination. |
| `frontend/src/features/master/services/broadcast-api.ts` | Typed `FormData` request builder and stable backend-error-to-i18n mapping. |
| `frontend/src/features/master/components/broadcast-composer.tsx` | Owns body, ordered `File[]`, local validation, submit state, outcome state, and dialog coordination. |
| `frontend/src/features/master/components/broadcast-attachment-list.tsx` | Renders ordered attachment metadata and accessible move/remove controls. |
| `frontend/src/features/master/components/broadcast-confirm-dialog.tsx` | Renders the explicit review/confirm control without any step-up password input. |
| `frontend/src/components/ui/textarea.tsx` | Shared styled textarea primitive used by the composer. |
| `frontend/src/features/master/services/__tests__/broadcast-api.spec.ts` | Tests `FormData` ordering, header generation, and error-key mapping. |
| `frontend/src/features/master/components/__tests__/broadcast-composer.spec.tsx` | Tests validation, reordering, mandatory confirmation, request behavior, and all outcome states. |
| `frontend/src/features/master/layout/__tests__/master-layout.spec.tsx` | Tests that Master navigation exposes Broadcast and non-Master state redirects to login. |

### Documentation

| Path | Responsibility |
|---|---|
| `docs/architecture/api-layer.md` | Documents `POST /api/v1/broadcasts`, Master authorization, multipart fields, outcome contract, and idempotency header. |
| `docs/architecture/frontend-architecture.md` | Documents the Master Broadcast route and composer responsibility. |
| `docs/how-to/configure-telegram-broadcast.md` | Operational runbook for the bot token, stable private/public channel chat ID, administrator permission, verification, and rotation. |
| `docs/how-to/publish-telegram-broadcast.md` | Diátaxis procedure for preparing MarkdownV2, selecting/reordering files, confirming, and handling partial delivery. |
| `docs/SUMMARY.md` | Adds both Telegram how-to entries under a How-to section. |

## Task 1: Build the Telegram delivery module

**Files:**
- Create: `backend/app/services/telegram_broadcast.py`
- Create: `backend/tests/test_telegram_broadcast.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`

**Interfaces:**
- Consumes: `telegram.Bot`, `telegram.InputFile`, the server-only `Settings` values, and a file-like object owned by FastAPI's upload layer.
- Produces: `BroadcastAttachment`, `BroadcastRequest`, `BroadcastOutcome`, `TelegramBroadcastClient` and `BroadcastValidationError`, all imported by `broadcast_service.py` and the API boundary in Task 2.

- [ ] **Step 1: Write failing validation and delivery tests**

Create `backend/tests/test_telegram_broadcast.py` with `pytestmark = pytest.mark.asyncio`. Cover the validation allow-list and ordered delivery with an injected `telegram.Bot` mock; the assertions must verify exact asynchronous bot-method order rather than only the final result.

```python
async def test_publish_sends_text_then_photo_video_and_document() -> None:
    def attachment(index: int, name: str, mime: str, kind: AttachmentKind) -> BroadcastAttachment:
        data = name.encode()
        return BroadcastAttachment(
            index=index, filename=name, content_type=mime, kind=kind,
            size=len(data), sha256=hashlib.sha256(data).hexdigest(), file=BytesIO(data),
        )

    bot = MagicMock()
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock(return_value=None)
    for method_name in ("send_message", "send_photo", "send_video", "send_document"):
        bot.attach_mock(AsyncMock(), method_name)
    publisher = TelegramBroadcastClient(bot=bot, chat_id="-100123")
    request = BroadcastRequest(
        body="*Release*",
        attachments=(
            attachment(0, "release.png", "image/png", "photo"),
            attachment(1, "walkthrough.mp4", "video/mp4", "video"),
            attachment(2, "notes.pdf", "application/pdf", "document"),
        ),
    )

    outcome = await publisher.publish(request)

    assert outcome.status == "published"
    assert outcome.delivered_attachment_indexes == (0, 1, 2)
    assert [call[0] for call in bot.method_calls] == [
        "send_message", "send_photo", "send_video", "send_document"
    ]


def test_rejects_a_mismatched_extension_and_content_type() -> None:
    with pytest.raises(BroadcastValidationError, match="broadcast_attachment_type_invalid"):
        validate_attachment("release.exe", "application/pdf", 12)
```

Also cover an empty body, 4,097 Unicode code points, an eleventh attachment, a synthetic attachment set exceeding the 500 MiB aggregate limit, a 50 MiB-plus-one-byte attachment, `telegram.error.BadRequest` entity parsing mapped to `broadcast_markup_invalid`, `telegram.error.Forbidden` mapped to `broadcast_permission_denied`, `telegram.error.RetryAfter` mapped to `broadcast_rate_limited`, and `telegram.error.NetworkError` mapped to `broadcast_unavailable`. Add a later-attachment exception test that returns `partial`, includes only prior indexes, and asserts no subsequent bot method is awaited.

- [ ] **Step 2: Run the new tests and confirm they fail before implementation**

Run:

```bash
cd backend && uv run pytest tests/test_telegram_broadcast.py -v
```

Expected: collection fails because `app.services.telegram_broadcast` does not exist.

- [ ] **Step 3: Add the maintained Telegram client, safe configuration, and the domain/adapter implementation**

Add the maintained async Telegram client and update its lockfile:

```bash
cd backend && uv add "python-telegram-bot>=22.5,<23.0"
```

Add the following empty-default fields to `Settings` and corresponding blank entries plus explanatory comments to `backend/.env.example`:

```python
telegram_bot_token: str = ""
telegram_broadcast_chat_id: str = ""
```

Implement `telegram_broadcast.py` with these concrete contracts:

```python
AttachmentKind = Literal["photo", "video", "document"]

@dataclass(frozen=True)
class BroadcastAttachment:
    index: int
    filename: str
    content_type: str
    kind: AttachmentKind
    size: int
    sha256: str
    file: BinaryIO

@dataclass(frozen=True)
class BroadcastRequest:
    body: str
    attachments: tuple[BroadcastAttachment, ...]

@dataclass(frozen=True)
class BroadcastOutcome:
    status: Literal["published", "partial", "failed"]
    delivered_attachment_indexes: tuple[int, ...]
    failure_code: str | None = None

class BroadcastPublisher(Protocol):
    async def publish(self, request: BroadcastRequest) -> BroadcastOutcome: ...

class BroadcastValidationError(ValueError):
    pass
```

Use one immutable allow-list mapping each allowed extension and MIME type to `photo`, `video`, or `document`. Keep `validate_body()` and `validate_attachment()` pure. At the composition root, create `Bot(token=settings.telegram_bot_token)` and inject it into `TelegramBroadcastClient`. `publish()` encloses the send sequence in `async with self._bot:` so `python-telegram-bot` initializes and shuts down its HTTPX request resources for the request. Inside that context the adapter calls `bot.send_message(chat_id, body, parse_mode=ParseMode.MARKDOWN_V2)`, then `send_photo`, `send_video`, or `send_document` for each attachment. Wrap every rewound file handle in `InputFile(file_handle, filename=attachment.filename, read_file_handle=False)` so the library's HTTPX backend streams it without loading a 50 MiB upload into memory. Catch exceptions in this order: `RetryAfter`, `Forbidden`, `BadRequest`, `NetworkError`, then `TelegramError`; map them to stable codes without logging exception payloads. Do not log the bot token, chat ID, body, filename, or bytes.

When text delivery fails, return `BroadcastOutcome("failed", (), code)`. Once text or any attachment has succeeded, return `partial` at the first later failure. Do not call another Telegram method after that failure.

- [ ] **Step 4: Run the focused backend tests until they pass**

Run:

```bash
cd backend && uv run pytest tests/test_telegram_broadcast.py -v
```

Expected: all adapter, validation, ordering, and safe-error mapping tests pass without network access.

- [ ] **Step 5: Format, lint, and commit the delivery module**

Run:

```bash
cd backend && uv run ruff check app/services/telegram_broadcast.py tests/test_telegram_broadcast.py && uv run ruff format --check app/services/telegram_broadcast.py tests/test_telegram_broadcast.py
```

Then commit only Task 1 files:

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/core/config.py backend/.env.example backend/app/services/telegram_broadcast.py backend/tests/test_telegram_broadcast.py
git commit -m "feat(telegram): add broadcast delivery adapter"
```

## Task 2: Expose the Master-only, idempotent broadcast endpoint

**Files:**
- Create: `backend/app/services/broadcast_service.py`
- Create: `backend/app/api/v1/endpoints/broadcasts.py`
- Create: `backend/app/schemas/broadcast.py`
- Create: `backend/tests/test_broadcast_service.py`
- Create: `backend/tests/test_broadcasts_api.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`
- Modify: `backend/tests/test_i18n.py`

**Interfaces:**
- Consumes: Task 1 domain types and `BroadcastPublisher`; `get_redis_manager()`; the two `Settings` Telegram values; multipart `UploadFile` input.
- Produces: `MasterGlobalUser`, `BroadcastService.publish(actor_id, idempotency_key, request) -> BroadcastOutcome`, and `POST /api/v1/broadcasts`, consumed by `publishBroadcast()` in Task 3.

- [ ] **Step 1: Write failing idempotency and ASGI endpoint tests**

Create `test_broadcast_service.py` with a `_FakeRedis` that implements `get()` and `set(..., nx=True, ex=600)` and a `_FakeManager.execute()` modeled after `test_step_up_limiter.py`. Use this concrete fake publisher that records calls.

```python
class RecordingPublisher:
    def __init__(self, outcome: BroadcastOutcome) -> None:
        self.outcome = outcome
        self.calls = 0

    async def publish(self, request: BroadcastRequest) -> BroadcastOutcome:
        self.calls += 1
        return self.outcome


async def test_same_completed_key_returns_cached_outcome_without_second_publish() -> None:
    publisher = RecordingPublisher(BroadcastOutcome("published", (0,), None))
    service = BroadcastService(_FakeManager(), publisher)
    request = BroadcastRequest(body="*Release*", attachments=())

    first = await service.publish("master-id", "request-1", request)
    second = await service.publish("master-id", "request-1", request)

    assert first == second
    assert publisher.calls == 1
```

Add tests for `broadcast_in_progress`, `broadcast_idempotency_conflict`, and a `RedisUnavailableError` becoming `broadcast_idempotency_unavailable` before publisher invocation. Inspect the fake Redis JSON and captured service logger records to assert they contain neither `*Release*`, attachment filenames, digests beyond the fingerprint, bot token, nor channel ID.

Create `test_broadcasts_api.py` with a local `_login()` helper like `test_i18n.py`. Patch the endpoint's service factory with a recording fake and post multipart data:

```python
response = await client.post(
    "/api/v1/broadcasts",
    data={"body": "*Release*"},
    files=[("attachments", ("notes.pdf", b"pdf", "application/pdf"))],
    headers={**headers, "Idempotency-Key": "request-1"},
)

assert response.status_code == 200
assert response.json() == {
    "status": "published",
    "delivered_attachment_indexes": [0],
    "failure_code": None,
}
```

Also assert unauthenticated requests receive `401`, a Tenant token receives `403`, and a Master token obtained after `POST /auth/switch-tenant` receives `403`; missing/blank idempotency keys and invalid multipart values receive stable validation details; missing Telegram setup returns `503` before the publisher runs; and a `partial` outcome returns `200` with its successful indexes. Extend `test_i18n.py` to assert both the English Master catalog and `t("es", ...)` include the new Broadcast title and error keys.

- [ ] **Step 2: Run the endpoint and service tests and confirm they fail**

Run:

```bash
cd backend && uv run pytest tests/test_broadcast_service.py tests/test_broadcasts_api.py tests/test_i18n.py -v
```

Expected: collection fails because the service, schema, and endpoint modules are absent.

- [ ] **Step 3: Add multipart support, the service seam, schemas, router, and translations**

Install the FastAPI multipart parser with the lockfile update required by the official FastAPI upload contract:

```bash
cd backend && uv add python-multipart
```

Implement the response model:

```python
class BroadcastOutcomeResponse(BaseModel):
    status: Literal["published", "partial", "failed"]
    delivered_attachment_indexes: list[int]
    failure_code: str | None
```

Implement `BroadcastService` with an injected Redis manager and `BroadcastPublisher`. Its request fingerprint is SHA-256 over the UTF-8 body plus each attachment's index, allowed media metadata, size, and content digest. The persisted JSON value contains only that fingerprint, `state` (`"in_progress"` or `"completed"`), terminal outcome status, indexes, and failure code. Its Redis key is derived from a SHA-256 digest of the Master ID and idempotency key; do not place the raw idempotency key in a Redis key or value.

Claim with `SET key value NX EX 600` through `RedisConnectionManager.execute()`. When the claim already exists, read it and return one of these stable application errors: `broadcast_in_progress` for a matching active claim, `broadcast_idempotency_conflict` for a different fingerprint, or the cached terminal `BroadcastOutcome` for a matching completed claim. Wrap unavailable/no Redis manager as `broadcast_idempotency_unavailable`; never invoke the publisher in that case. Replace a successful claim with the terminal outcome using the same 600-second TTL.

The endpoint must use FastAPI `Form`, `File`, and `UploadFile` parameters rather than a JSON body. It receives `body: Annotated[str, Form()]`, `attachments: Annotated[list[UploadFile], File()]`, and `idempotency_key: Annotated[str, Header(alias="Idempotency-Key")]`. While converting each upload, hash it in 64 KiB chunks, enforce the per-file and aggregate size limits, validate its extension/MIME pair, rewind it with `await upload.seek(0)`, and build `BroadcastAttachment`. Close every upload in a `finally` block.

Add `require_master_global_context()` to `app/api/dependencies.py`. It must depend on the existing current-user resolution, require `current_user.role == "master"`, decode the bearer access token already supplied by `oauth2_scheme`, and reject any payload with a non-null `active_tenant_id` using `HTTPException(403, detail="master_global_context_required")`. Export `MasterGlobalUser = Annotated[User, Depends(require_master_global_context)]` and use it as the broadcasts endpoint's only user dependency. Construct `TelegramBroadcastClient` only after preflight configuration confirms both settings are non-empty. Return `BroadcastOutcomeResponse` for all three delivery outcomes. Map local validation to `422`, absent config or Redis to `503`, support-context or key-reuse conflict/in-progress to `409` or `403` as stated, each with only its stable code in `detail`. Add `broadcasts.router` to `api_router`.

Add complete English and Spanish `frontend.master.broadcast.*` strings for navigation, title, MarkdownV2 guidance, attachment limits, confirmation, every result state, and each stable error code. Preserve the existing user-owned modification in `catalogs_en_general.py`; all Broadcast strings belong in the two frontend catalog files.

- [ ] **Step 4: Run focused tests and backend style checks**

Run:

```bash
cd backend && uv run pytest tests/test_telegram_broadcast.py tests/test_broadcast_service.py tests/test_broadcasts_api.py tests/test_i18n.py -v
cd backend && uv run ruff check app/api/v1/endpoints/broadcasts.py app/schemas/broadcast.py app/services/broadcast_service.py app/services/telegram_broadcast.py tests/test_broadcast_service.py tests/test_broadcasts_api.py
cd backend && uv run ruff format --check app/api/v1/endpoints/broadcasts.py app/schemas/broadcast.py app/services/broadcast_service.py app/services/telegram_broadcast.py tests/test_broadcast_service.py tests/test_broadcasts_api.py
```

Expected: all focused tests pass; ruff reports no violations.

- [ ] **Step 5: Commit the endpoint slice without unrelated i18n work**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/api/v1/endpoints/broadcasts.py backend/app/api/v1/router.py backend/app/schemas/broadcast.py backend/app/services/broadcast_service.py backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py backend/tests/test_broadcast_service.py backend/tests/test_broadcasts_api.py backend/tests/test_i18n.py
git commit -m "feat(telegram): add idempotent master broadcast endpoint"
```

Before committing, use `git diff --cached --name-only` and confirm `backend/app/core/i18n/catalogs_en_general.py` is absent.

## Task 3: Deliver the Master Broadcast Composer

**Files:**
- Create: `frontend/src/components/ui/textarea.tsx`
- Create: `frontend/src/features/master/services/broadcast-api.ts`
- Create: `frontend/src/features/master/components/broadcast-composer.tsx`
- Create: `frontend/src/features/master/components/broadcast-attachment-list.tsx`
- Create: `frontend/src/features/master/components/broadcast-confirm-dialog.tsx`
- Create: `frontend/src/routes/master/broadcast.tsx`
- Create: `frontend/src/features/master/services/__tests__/broadcast-api.spec.ts`
- Create: `frontend/src/features/master/components/__tests__/broadcast-composer.spec.tsx`
- Create: `frontend/src/features/master/layout/__tests__/master-layout.spec.tsx`
- Modify: `frontend/src/features/master/layout/master-layout.tsx`
- Modify: `frontend/src/routeTree.gen.ts` (generated only by `npm run build`)

**Interfaces:**
- Consumes: `POST /broadcasts` response `{ status, delivered_attachment_indexes, failure_code }` from Task 2 and catalog keys added there.
- Produces: `publishBroadcast(body: string, attachments: File[], idempotencyKey: string): Promise<BroadcastOutcome>`, the `/master/broadcast` route, and the Master composer UI.

- [ ] **Step 1: Write failing API, composer, and navigation tests**

In `broadcast-api.spec.ts`, mock `@/lib/api` and verify that `publishBroadcast()` appends `body` once, appends `attachments` in the supplied order under the exact `attachments` field name, and sends an `Idempotency-Key` header.

```ts
it("preserves attachment order in the multipart request", async () => {
  const first = new File(["one"], "first.pdf", { type: "application/pdf" });
  const second = new File(["two"], "second.png", { type: "image/png" });

  await publishBroadcast("*Release*", [first, second], "request-1");

  const form = vi.mocked(api.post).mock.calls[0][1] as FormData;
  expect(form.get("body")).toBe("*Release*");
  expect(form.getAll("attachments").map((file) => (file as File).name)).toEqual([
    "first.pdf",
    "second.png",
  ]);
})
```

In `broadcast-composer.spec.tsx`, mock `publishBroadcast()` and `@/i18n`. Test an empty body warning, rejection of an eleventh file and a mismatched `File` type/name, accessible move-up/move-down ordering, absence of a request before confirmation, submission after confirmation with `crypto.randomUUID()`'s key, and visible `published`, `partial`, and `failed` result messages.

In `master-layout.spec.tsx`, mock `useAuthStore()` as a global Master and assert a navigation link targets `/master/broadcast`; mock the same Master with a non-null `activeTenantId` and assert the link is absent; mock a Tenant and assert the layout redirects to `/login`.

- [ ] **Step 2: Run frontend tests and confirm they fail**

Run:

```bash
cd frontend && npm test -- broadcast-api.spec.ts broadcast-composer.spec.tsx master-layout.spec.tsx
```

Expected: Vitest fails to resolve the new service and component modules.

- [ ] **Step 3: Add typed request client, focused components, route, and navigation**

Create `textarea.tsx` as a styled native `<textarea>` that uses `React.ComponentProps<"textarea">` and the existing `cn()` helper; it exports `Textarea` and forwards standard `<textarea>` props without adding a dependency.

In `broadcast-api.ts`, define and export:

```ts
export type BroadcastStatus = "published" | "partial" | "failed";

export interface BroadcastOutcome {
  status: BroadcastStatus;
  delivered_attachment_indexes: number[];
  failure_code: string | null;
}

export async function publishBroadcast(
  body: string,
  attachments: File[],
  idempotencyKey: string,
): Promise<BroadcastOutcome> {
  const form = new FormData();
  form.append("body", body);
  attachments.forEach((file) => form.append("attachments", file));
  const { data } = await api.post<BroadcastOutcome>("/broadcasts", form, {
    headers: { "Idempotency-Key": idempotencyKey },
  });
  return data;
}
```

Add `mapBroadcastError(error, fallbackKey)` patterned after `mapExecutorError()`, mapping every Task 2 stable detail code to the matching `frontend.master.broadcast.error_*` catalog key.

Keep the browser validation constants local to the Broadcast feature and identical to the backend contract: `MAX_ATTACHMENTS = 10`, `MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024`, `MAX_BODY_CODE_POINTS = 4096`, plus the same extension/MIME mapping. Count body code points with `Array.from(body).length`.

`BroadcastAttachmentList` receives `files`, `onMove(index, direction)`, and `onRemove(index)`; render each filename, formatted size, type label, and buttons with unambiguous accessible labels such as `Move attachment 2 up` and `Remove attachment 2`. It must preserve the selected order.

`BroadcastConfirmDialog` receives `open`, `body`, `files`, `submitting`, `onCancel`, and `onConfirm`; render the exact MarkdownV2 source and attachment names/sizes, explain that delivery is immediate, and disable its action while submitting. It uses the existing `AlertDialog` primitives and contains no password field.

`BroadcastComposer` owns a controlled body, `File[]`, validation message, dialog state, submitting state, and final outcome. It displays MarkdownV2-only guidance, a multiple input with the allowed extensions in `accept`, and the attachment list. It runs local validation before opening the dialog. On confirmed submission, create one UUID, call `publishBroadcast`, retain the returned outcome for display, and close the dialog. Do not clear the form after `partial` or `failed`; the Master needs the local data to decide whether to publish a follow-up. Prevent a second submission while `submitting` is true.

Create the TanStack route with `createFileRoute("/master/broadcast")`. Add a `Send` icon navigation item in `MasterLayout` between Dashboard and Lookup Executors only when `activeTenantId` is null; a Master support-context session must not see the Broadcast destination. Run the build to regenerate, never hand-edit, `routeTree.gen.ts`.

- [ ] **Step 4: Run targeted frontend tests, lint, and build**

Run:

```bash
cd frontend && npm test -- broadcast-api.spec.ts broadcast-composer.spec.tsx master-layout.spec.tsx
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: targeted tests pass, lint passes, TypeScript succeeds, and the generated route tree contains `/master/broadcast`.

- [ ] **Step 5: Commit the Master UI slice**

```bash
git add frontend/src/components/ui/textarea.tsx frontend/src/features/master/services/broadcast-api.ts frontend/src/features/master/components/broadcast-composer.tsx frontend/src/features/master/components/broadcast-attachment-list.tsx frontend/src/features/master/components/broadcast-confirm-dialog.tsx frontend/src/routes/master/broadcast.tsx frontend/src/features/master/services/__tests__/broadcast-api.spec.ts frontend/src/features/master/components/__tests__/broadcast-composer.spec.tsx frontend/src/features/master/layout/__tests__/master-layout.spec.tsx frontend/src/features/master/layout/master-layout.tsx frontend/src/routeTree.gen.ts
git commit -m "feat(master): add Telegram broadcast composer"
```

## Task 4: Publish operator documentation and run release verification

**Files:**
- Create: `docs/how-to/configure-telegram-broadcast.md`
- Create: `docs/how-to/publish-telegram-broadcast.md`
- Modify: `docs/SUMMARY.md`
- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/frontend-architecture.md`

**Interfaces:**
- Consumes: the endpoint, configuration names, result semantics, and UI behavior from Tasks 1–3.
- Produces: safe, procedural operator documentation linked from the documentation index.

- [ ] **Step 1: Draft the two how-to guides against the implemented behavior**

Write `configure-telegram-broadcast.md` as a procedure that:

1. creates the bot and stores the token only in the production secret manager;
2. adds the bot as a channel administrator with permission to publish;
3. obtains and configures the stable `TELEGRAM_BROADCAST_CHAT_ID` for either a public or private channel without treating `t.me/trackpal` as the identifier;
4. configures `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BROADCAST_CHAT_ID`, redeploys, and verifies with a deliberate non-production test post; and
5. rotates a compromised token by revoking it, updating the secret, redeploying, and testing again.

Do not place a token, channel ID, customer data, or real production command in the guide.

Write `publish-telegram-broadcast.md` as a Diátaxis how-to with prerequisites, a MarkdownV2 note, the precise example `Release v2\.0 is *live*\!`, attachment selection/reordering, confirmation, result interpretation, and partial-delivery response. State explicitly that earlier messages cannot be undone by TrackPal and that a follow-up is a new, manual Broadcast.

- [ ] **Step 2: Update architecture docs and the summary index**

Add the endpoint to the API route table and document its multipart fields, `Idempotency-Key`, global-Master-only auth, 200 outcome shape, and 403/409/422/503 preflight failures in `docs/architecture/api-layer.md`.

Add `/master/broadcast`, `BroadcastComposer`, the local ordered-file behavior, and the no-secret browser boundary to `docs/architecture/frontend-architecture.md`.

Add a `## How-to Guides` table to `docs/SUMMARY.md` containing links and concise descriptions for both new Telegram guides. Keep existing lookup-executor deployment links unchanged.

- [ ] **Step 3: Review documentation links and run the complete feature verification set**

Run:

```bash
cd backend && uv run pytest
cd backend && uv run ruff check app tests
cd backend && uv run ruff format --check app tests
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

Then inspect the changed Markdown links manually: both how-to paths must resolve from `docs/SUMMARY.md`, each guide must link to the other where specified, and no guide contains a real credential or channel ID.

- [ ] **Step 4: Commit the documentation and verification-ready feature**

```bash
git add docs/how-to/configure-telegram-broadcast.md docs/how-to/publish-telegram-broadcast.md docs/SUMMARY.md docs/architecture/api-layer.md docs/architecture/frontend-architecture.md
git commit -m "docs: add Telegram broadcast operator guides"
```

Before committing, run `git status --short` and confirm the pre-existing `backend/app/core/i18n/catalogs_en_general.py` modification remains unstaged and untouched.

## Plan Self-Review

### Spec coverage

- Single global-Master-only configured channel, server-only secrets, `python-telegram-bot` adapter, and support-context rejection: Tasks 1 and 2.
- MarkdownV2 body, ten ordered file attachments, exact type/size limits, text-first sequential delivery, and no albums: Tasks 1–3.
- Manual confirmation, no LLM integration, no scheduling/history/retries/rollback: Task 3 and the global constraints.
- Redis ten-minute idempotency, safe cached result, conflict/in-progress behavior, and fail-closed infrastructure handling: Task 2.
- Safe result/error mapping, redacted logs/state, backend and frontend i18n: Tasks 1 and 2.
- Route, navigation, responsive Master composer behavior, typed multipart client, and browser tests: Task 3.
- API/frontend architecture docs, configuration guide, publishing how-to, and `SUMMARY.md`: Task 4.
- Backend targeted checks, frontend suite/lint/build, and documentation link review: Task 4.

### Placeholder scan

The plan contains concrete paths, public interfaces, test assertions, commands, limits, headers, stable error codes, and commit commands. It does not defer any implementation decision.

### Type consistency

`BroadcastOutcome`, `BroadcastStatus`, `delivered_attachment_indexes`, `failure_code`, the multipart field `attachments`, and the `Idempotency-Key` header use the same names across Tasks 1–3. `BroadcastService.publish()` is the only service entry point the endpoint calls, while `TelegramBroadcastClient` satisfies the `BroadcastPublisher` seam.

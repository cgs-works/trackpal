# Private Help release gate

This is the release checklist for the first private Help artifact. It is a **how-to guide for release owners**, not a user manual.

## Release policy

Private Help has one frontend gate: `VITE_PRIVATE_HELP_ENABLED`. The default is `false` in `frontend/.env.example`. Keep it off until every automated check and every manual QA row below is complete. The same value enables or disables Help navigation, the Help Center, contextual Help, and Tenant Admin tours for both supported audiences.

Never enable Tenant Admin Help and Client Help with separate flags. Never publish a frontend build with the flag enabled before the backend artifact has passed the release contract.

## Automated release checks

Run these commands from a clean checkout of the release commit:

```bash
cd backend
uv run python -m scripts.verify_help_release
uv run pytest

cd ../frontend
npm test -- --run
npm run build
```

The release contract verifies all of the following before the checked-in artifact can be published:

- Spanish and English topic sets are complete and identical in metadata.
- Tenant Admin and Client manuals are both present.
- The authorized search index contains every topic in both locales.
- Starter, initial Pro, and Starter-to-Pro tour releases are present with their approved step counts.
- Client topics do not declare an orientation tour.
- Artifact schema and frontend target-contract versions are compatible.
- The checked-in artifact contains the same compiled data as the Markdown sources.

A target-contract mismatch may keep the manual available at runtime, but it must disable the tour. The release check itself must still pass against the current frontend target contract.

## Manual browser QA matrix

Record the browser, viewport, locale, account/plan, result, and evidence link for every row. A row is complete only when the Help Center is private, the article and search results are authorized, navigation is responsive, focus and keyboard behavior work, and no Help action mutates product data.

| Surface | Locale | Viewport | Required checks | Status |
|---|---|---|---|---|
| Tenant Admin Starter | Spanish | Desktop | Manual topics, search, contextual Help, Starter tour | Pending sign-off |
| Tenant Admin Starter | Spanish | Mobile | Drawer, full-width article, mobile tour Sheet | Pending sign-off |
| Tenant Admin Starter | English | Desktop | Manual topics, search, contextual Help, Starter tour | Pending sign-off |
| Tenant Admin Starter | English | Mobile | Drawer, full-width article, mobile tour Sheet | Pending sign-off |
| Tenant Admin Pro | Spanish | Desktop | Pro topics/search, contextual Help, Pro tour | Pending sign-off |
| Tenant Admin Pro | Spanish | Mobile | Drawer, Pro topics, mobile tour Sheet | Pending sign-off |
| Tenant Admin Pro | English | Desktop | Pro topics/search, contextual Help, Pro tour | Pending sign-off |
| Tenant Admin Pro | English | Mobile | Drawer, Pro topics, mobile tour Sheet | Pending sign-off |
| Client manual | Spanish | Desktop | Client-only topics/search, no tour | Pending sign-off |
| Client manual | Spanish | Mobile | Client drawer, article layout, no tour | Pending sign-off |
| Client manual | English | Desktop | Client-only topics/search, no tour | Pending sign-off |
| Client manual | English | Mobile | Client drawer, article layout, no tour | Pending sign-off |

The manual scenarios must also cover:

- initial, completed, skipped, replayed, and feature-update releases;
- Starter-to-Pro upgrade and Pro-to-Starter downgrade, including the preserved-data/paused-automation notice;
- Help API failure with Retry and no tour acknowledgement;
- artifact/target mismatch with manual access but no tour;
- missing required and explicitly conditional targets;
- route transitions, safe Settings panels, keyboard-only operation, focus restoration, reduced motion, translated long copy, and all seven approved tour steps.

## Topic inventory

| Topic ID | Plans | Tab | Notes |
|---|---|---|---|
| `tenant-admin.country` | Starter, Pro | Regional (My Account) | Country selection (ISO code) |
| `tenant-admin.currency` | Pro | Regional (My Account) | Currency display for plan prices |
| `tenant-admin.language` | Starter, Pro | Regional (My Account) | Language picker relocated from old locale tab |
| `tenant-admin.timezone` | Pro | Regional (My Account) | Timezone relocated from old timezone tab |
| `tenant-admin.catalog` | Pro | — | Added plan prices paragraph |
| `client.subscriptions` | Pro | — | Added plan price display note |

## Release evidence

The first implementation deliberately does not add automated browser E2E. Vitest, pytest, the compiler contract, and the production build cover deterministic behavior; the matrix above is the required human verification for browser layout, focus, responsive presentation, and real route transitions.

A local browser smoke run on 2026-07-21 verified the following against an ephemeral SQLite backend and a Vite build with the gate enabled:

- Pro Tenant Admin in English: Help appears in desktop navigation, Pro-only topics are visible, search returns an authorized result, and contextual Help opens the Dashboard topic.
- Client in English: the mobile navigation exposes Dashboard, Profile, and Help; the Client manual loads without Tenant Admin topics or a tour.
- Starter Tenant Admin in Spanish: the mobile navigation exposes Dashboard, Settings, and Help but not Pro modules; Starter Help loads without Pro topics.
- Unauthenticated direct navigation to `/admin/help` redirects to login.

This smoke run is evidence for the listed paths, not a substitute for the complete matrix. The remaining desktop/mobile, locale, tour lifecycle, failure, accessibility, version-mismatch, and regional-settings rows still require human sign-off before production enablement.

Attach the completed QA notes to the issue or release record. Until every row is signed off, leave `VITE_PRIVATE_HELP_ENABLED=false` in the deployed frontend environment.

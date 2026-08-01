# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Master operators, tenant admins, and clients using TrackPal across web dashboards and WhatsApp workflows. Master operators manage tenant lifecycle and global code-service availability; tenant admins manage clients, catalog, subscriptions, mailbox connections, and access-code workflows; clients use limited self-service for profile/password tasks. Users are often working in Spanish-first operational contexts where speed, trust, and low ambiguity matter.

## Product Purpose

TrackPal is a multi-tenant platform for WhatsApp-based service delivery, streaming-account subscription management, and mailbox code retrieval. It centralizes tenant and client operations, keeps WhatsApp console flows aligned with REST/dashboard workflows, and reduces manual handling of access codes, subscription status, and tenant support.

## Positioning

A role-aware operations console that keeps multi-tenant dashboard workflows, WhatsApp identity, subscriptions, mailboxes, and access-code handling aligned in one system.

## Operating Context

Master operators and tenant admins use the web dashboard for repeat operational work: tenant lifecycle, catalog and subscriptions, client management, mailbox connections, settings, and access-code workflows. WhatsApp remains a text-first operational channel, while REST APIs and public catalog surfaces support integrations and client-facing workflows.

## Capabilities and Constraints

- Supports master, tenant-admin, and client roles with explicit role boundaries.
- Integrates WhatsApp workflows, REST APIs, PostgreSQL-backed business data, and Redis-backed session state.
- Tenant admins can manage clients, catalog services and plans, subscriptions, mailboxes, settings, and optional service icons.
- Spanish and English flows must remain resilient to longer translated labels and validation messages.
- Credentials, mailbox data, access codes, and WhatsApp identity require trustworthy handling and explicit risk states.
- Prefer familiar controls and preserve text-only WhatsApp messages where visual UI is unavailable.

## Brand Commitments

- Product name: TrackPal.
- Brand personality: calm operator; precise, reliable, quietly confident, and task-focused.
- The interface should feel like a dependable operations console, not a marketing demo.
- Avoid generic SaaS-card aesthetics, gradient hero text, decorative dashboard effects, and startup-template polish that do not improve operator confidence or task completion.

## Evidence on Hand

- Implemented React web dashboard under `frontend/` with role-aware routes and shared shadcn/ui components.
- Backend and domain documentation under `docs/` covering architecture, workflows, integrations, subscriptions, help, export, and deletion.
- Existing design system documented in `DESIGN.md` and grounded in the project's frontend tokens and components.

## Product Principles

1. Put operational clarity before decoration.
2. Make role boundaries obvious.
3. Keep bilingual Spanish/English flows resilient.
4. Preserve trust around credentials, mailboxes, and WhatsApp identity.
5. Prefer familiar controls over invented affordances.

## Accessibility & Inclusion

Target WCAG 2.2 AA with extra scrutiny for Spanish-first and bilingual layouts: keyboard access, visible focus, reduced-motion alternatives, sufficient contrast, non-color-only status cues, and label/copy patterns that survive longer translated text.

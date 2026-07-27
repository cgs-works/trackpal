# Demo Tenants use browser-local workspaces with a server-enforced lifecycle

TrackPal represents each Demo Tenant as a flagged Tenant with an immutable Master-selected Starter or Pro plan. The backend persists only its authentication identity and evaluation lifecycle; each browser owns the plan-aware business profile, settings, simulated integrations, and Pro business records in a versioned Demo Workspace.

The backend starts a non-extendable 48-hour evaluation on the first successful Demo Credentials login, exposes a lifecycle heartbeat, and rejects real tenant business persistence, external integrations, Public API Catalog access, export, and self-deletion. An expired demo is removed by its next request or manually by the Master.

This boundary was chosen over database-persisted sandbox data or a parallel demo-account model because it reuses TrackPal authentication while preventing demo activity from reaching production systems. The tradeoffs are independent browser state, no Master preview or telemetry, and the cost of maintaining production-equivalent frontend behavior.

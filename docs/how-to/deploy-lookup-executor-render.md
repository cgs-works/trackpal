# Deploy a Lookup Executor on Render Free

This runbook deploys the reference `worker/` application as a Render Free
**Web Service**. Render background workers do not have a Free instance type.
The service is independent from the TrackPal backend and has no PostgreSQL or
Redis access.

## 1. Create the draft in TrackPal

1. Sign in as Master and open **Lookup Executors**.
2. Create a draft with a descriptive name, provider label, and capacity `1`.
3. Copy the displayed executor ID and protocol secret immediately. The secret
   is shown only once. Store it in a password manager until the Render service
   is configured.
4. Keep the draft disabled until the first challenge succeeds.

## 2. Create the Render service

1. In Render, create a **New > Web Service** from the TrackPal repository.
2. Set **Root Directory** to `worker/`.
3. Use the Python runtime and these commands:

   ```text
   Build Command: pip install uv && uv sync --frozen
   Start Command: uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

4. Select the Free plan. Free instances sleep after inactivity and may take
   approximately one minute to wake. The workspace shares 750 Free instance
   hours per month across its services.
5. Add these environment variables without quotes around the values:

   | Variable | Value |
   |---|---|
   | `TRACKPAL_EXECUTOR_ID` | The copied draft UUID |
   | `TRACKPAL_EXECUTOR_SECRET` | The copied one-time secret |
   | `TRACKPAL_MAX_CONCURRENCY` | `1` |

   Render's `worker/render.yaml` contains the same Blueprint configuration;
   `sync: false` keeps the ID and secret as manually supplied values.
6. Deploy and wait for the service to become live.

## 3. Register and verify the URL

1. Copy the Render service URL, for example `https://trackpal-lookup-executor.onrender.com`.
2. Paste it into the draft's **Base URL**. Keep the URL HTTPS and do not add a
   trailing job path.
3. Use **Test** to wake the service and run a signed challenge. Confirm that
   the response reports protocol version `1`, the expected executor ID, and
   capacity `1`.
4. Use **Verify** to establish trust, then **Activate**. Activation is blocked
   until the destination is verified.

The first test can take up to the expected one-minute cold start. A successful
challenge is the manual health test; TrackPal does not run a permanent ping
loop. The executor only receives signed, encrypted commands and sends signed,
encrypted callbacks.

## 4. Operations

- Monitor the shared 750-hour workspace budget and the executor's health and
  capacity in TrackPal. Free sleeping is expected, not an application failure.
- To rotate the secret, choose **Rotate**, copy the pending one-time secret,
  replace `TRACKPAL_EXECUTOR_SECRET` in Render, redeploy, run **Verify**, and
  confirm promotion before removing the old deployment value.
- To disable an executor, disable it in TrackPal first. Existing leases are
  allowed to reconcile; pending jobs can be assigned to another active
  executor.
- For rollback, redeploy the last known-good Render deployment and restore the
  previously verified secret. If the URL or transport changed, run **Test** and
  **Verify** again before activating. Do not claim a deployment rollback was
  tested locally.

## Local checks before release

```bash
cd worker
uv run pytest
uv run ruff check app tests
uv run ruff format --check app tests
```

A real Render deployment, cold start, URL reachability, workspace-hour usage,
and Master challenge must be verified manually during release. Local tests do
not prove those external conditions.

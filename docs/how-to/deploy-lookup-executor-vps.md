# Deploy a Lookup Executor on Docker or a VPS

This runbook deploys `worker/` independently of the backend. The executor
needs outbound access to Gmail and to the TrackPal callback URL, but never
needs PostgreSQL or Redis credentials.

## 1. Enroll the executor

Create a draft in TrackPal as Master, copy the one-time executor ID and
protocol secret, and keep the draft disabled. The values below are examples;
replace them with the enrollment values and never commit them.

## 2. Build and run the container

From the repository root:

```bash
docker build -t trackpal-lookup-executor ./worker
docker run -d \
  --name trackpal-lookup-executor \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e TRACKPAL_EXECUTOR_ID='00000000-0000-0000-0000-000000000000' \
  -e TRACKPAL_EXECUTOR_SECRET='replace-with-enrollment-secret' \
  -e TRACKPAL_MAX_CONCURRENCY='1' \
  trackpal-lookup-executor
```

The image uses Python 3.12 slim, installs the locked uv environment, and runs
as the non-root `trackpal` user. Port `8000` is bound to loopback in this
example because Caddy will provide the public HTTPS endpoint.

A Compose-equivalent deployment can use the same image and environment:

```yaml
services:
  executor:
    build: ./worker
    restart: unless-stopped
    environment:
      TRACKPAL_EXECUTOR_ID: ${TRACKPAL_EXECUTOR_ID}
      TRACKPAL_EXECUTOR_SECRET: ${TRACKPAL_EXECUTOR_SECRET}
      TRACKPAL_MAX_CONCURRENCY: "1"
    ports:
      - "127.0.0.1:8000:8000"
```

Use a secrets manager or a root-readable environment file outside the Git
checkout. Do not put real values in `docker-compose.yml`, the image, or logs.

For a direct public-IP `http_encrypted` deployment (the exception in section
4), replace the loopback binding with an all-interface binding:

```bash
docker run -d \
  --name trackpal-lookup-executor \
  --restart unless-stopped \
  -p 0.0.0.0:8000:8000 \
  -e TRACKPAL_EXECUTOR_ID='00000000-0000-0000-0000-000000000000' \
  -e TRACKPAL_EXECUTOR_SECRET='replace-with-enrollment-secret' \
  -e TRACKPAL_MAX_CONCURRENCY='1' \
  trackpal-lookup-executor
```

This direct-public command is not needed when Caddy is the public endpoint.

## 3. Firewall and HTTPS

Allow only the ports required by the deployment. For a Caddy setup, expose
public TCP `80` and `443`; keep executor TCP `8000` closed to the Internet.
For example, with UFW:

```bash
sudo ufw default deny incoming
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

For the direct public-IP command above, allow the published executor port as
well:

```bash
sudo ufw allow 8000/tcp
```

The `8000/tcp` rule is required for direct public access; a firewall rule alone
cannot expose a service that Docker bound to `127.0.0.1`. Do not add this rule
for the Caddy/HTTPS loopback deployment.

Point a DNS name at the VPS and use Caddy:

```caddyfile
executor.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Caddy obtains and renews the public certificate automatically when DNS and
ports `80`/`443` are correct. A temporary DNS-free name can use `sslip.io`:

```caddyfile
203-0-113-10.sslip.io {
    reverse_proxy 127.0.0.1:8000
}
```

Replace `203-0-113-10` with the VPS public IP. The direct IP itself is not a
normal certificate name: a public-IP certificate requires a CA and certificate
provider that explicitly supports IP SANs, and many automated ACME flows do
not. Prefer a domain or `sslip.io` name.

After Caddy is live, set that HTTPS URL as the draft Base URL. Run **Test**,
then **Verify**, and activate only after the challenge reports protocol `1`,
the expected executor ID, and capacity `1`.

## 4. Explicit public-IP HTTP exception

HTTPS is required by default. If a deployment must use a public IP with
`http://`, configure the TrackPal executor transport as `http_encrypted` and
complete the Master step-up confirmation by typing **ALLOW HTTP**. This is an
explicit risk acceptance, not a way to bypass protocol security: AES-GCM
application encryption, HMAC signing, timestamp checks, and nonce replay
protection remain mandatory. Never use ordinary `http` transport for mailbox
credentials or results.

The `http_encrypted` exception still requires a reachable public IP and the
`sudo ufw allow 8000/tcp` rule when using the direct port-8000 command above.
If the endpoint changes, disable it, update the destination, run a new
challenge, and re-verify before activation.

## 5. Health, rotation, upgrade, and rollback

### Simple in-place rebuild

For a straightforward upgrade where brief downtime is acceptable, update the
repository, remove the current container, rebuild the existing image tag, and
recreate the container with the same executor ID and active secret:

```bash
cd /path/to/trackpal
git pull --ff-only

docker stop trackpal-lookup-executor
docker rm trackpal-lookup-executor
docker build -t trackpal-lookup-executor ./worker

docker run -d \
  --name trackpal-lookup-executor \
  --restart unless-stopped \
  --env-file /root/trackpal-executor.env \
  -p 127.0.0.1:8000:8000 \
  trackpal-lookup-executor
```

Confirm that the recreated container is running before using the Master
challenge:

```bash
curl -fsS http://127.0.0.1:8000/healthz
docker logs --tail 100 trackpal-lookup-executor
```

The health endpoint should return `{"status":"ok"}`. Then run **Test** and
**Verify** from TrackPal Master. Preserve `TRACKPAL_EXECUTOR_ID` and
`TRACKPAL_EXECUTOR_SECRET`; do not enroll a new executor for a normal upgrade.

This approach is valid, but stopping and removing the container before the
build creates downtime. Reusing the unversioned image tag also removes the
simple image-based rollback path. Prefer the versioned-image procedure below
when uninterrupted service or fast rollback is required.

- The Master **Test** action is the signed manual health check. A local
  `curl` to the root is not a protocol health test and may return `404`.
- To rotate, choose **Rotate** in TrackPal, replace the container secret with
  the pending value, restart or recreate the container, run **Verify**, and
  confirm promotion. Keep the previous container available until promotion is
  confirmed.
- Upgrade by building a versioned image, stopping the old container only after
  the new one has started, and running the Master challenge. Preserve the
  current executor ID and secret unless performing a planned rotation.
- Roll back by restarting the previous image with the current active protocol
  secret, then run **Test** and **Verify**. If the base URL or transport
  changed, activation must remain disabled until re-verification succeeds.

```bash
docker pull trackpal-lookup-executor:previous
docker stop trackpal-lookup-executor
docker rm trackpal-lookup-executor
# Re-run the docker run command with the previous image and current active secret.
```

## Local checks before release

```bash
cd worker
uv run pytest
uv run ruff check app tests
uv run ruff format --check app tests
```

The VPS firewall, DNS, certificate issuance, public reachability, Docker
restart behavior, and Master challenge are manual release checks; they cannot
be verified by the repository test suite.

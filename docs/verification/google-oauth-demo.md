# Google OAuth Verification Demo

Use the synthetic **TrackPal Demo** code service when recording the Gmail
`gmail.readonly` verification video. It avoids displaying third-party streaming
brands or real customer data while exercising the production lookup path.

## Demo values

- Service: `TrackPal Demo`
- Subject: `Your TrackPal demo access code`
- Expected code: `864215`
- HTML message: [trackpal-demo-code-email.html](trackpal-demo-code-email.html)

## Prepare the service

1. Apply the latest Alembic migration. The migration creates the globally active
   `trackpal_demo` service.
2. In the verification account's Settings, enable **TrackPal Demo** under code
   services. Existing accounts do not select the new service automatically.
3. Connect the Gmail test mailbox through the normal TrackPal OAuth flow.

## Send the synthetic message

1. Open `trackpal-demo-code-email.html` in a browser.
2. Copy the rendered message and paste it into an email composer that preserves
   HTML formatting.
3. Send it to the connected Gmail test address with the exact subject:
   `Your TrackPal demo access code`.
4. Start the WhatsApp lookup within five minutes of receiving the message.
5. Select **TrackPal Demo**, enter the same recipient address, and confirm.
6. The expected WhatsApp result is `864215`.

The recipient entered in WhatsApp must match the message's `To` or `Cc` address.
Use only test accounts and synthetic data in the recording.

## After recording

Disable **TrackPal Demo** globally from the Master code-services panel. Tenant
selections can remain stored because globally inactive services are excluded
from the effective WhatsApp list.

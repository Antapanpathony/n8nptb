# n8n ↔ Telegram polling bridge

A self-hosted bridge that lets n8n receive and send Telegram messages
without ever exposing a public HTTPS endpoint.

## Why this exists

n8n's built-in **Telegram Trigger** node works via a Telegram webhook, and
Telegram webhooks require a publicly reachable HTTPS URL with a valid
certificate — port forwarding, a reverse proxy, a domain, a cert, or a
tunnel (ngrok, Cloudflare Tunnel, etc.) if you're running n8n at home or
behind NAT.

**Long polling avoids all of that.** The bridge in this repo runs
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
in polling mode: it opens outbound connections to Telegram's servers and
asks "any new messages?" in a loop. No inbound port, no certificate, no
tunnel — the only two things listening on this host are:

- the bridge's own HTTP API, bound to `127.0.0.1:8811` (loopback only)
- n8n itself, bound to whatever host/port it normally runs on (typically
  also loopback, e.g. `localhost:5678`)

Nothing in this design accepts a connection from outside the machine.

## Architecture

```
Telegram servers
      │  (bridge polls outbound; no inbound port)
      ▼
telegram_bridge (Python, asyncio)
  ├─ long-polling loop ──POST──▶ n8n Webhook node (http://localhost:5678/webhook/telegram-in)
  └─ FastAPI on 127.0.0.1:8811 ◀──POST── n8n "Telegram Bridge" node (Send Message)
```

- **Component 1 — `telegram_bridge/`**: the Python polling service. Runs
  the Telegram long-polling loop and a small FastAPI app in one process
  (`asyncio.gather`), fully async.
- **Component 2 — n8n receive side**: just n8n's built-in **Webhook**
  node, listening at `/webhook/telegram-in`. No custom code — it's plain
  localhost HTTP between the bridge and n8n, so n8n's public-HTTPS
  requirement for Telegram never applies here, because it's the *bridge*,
  not n8n, that talks to Telegram.
- **Component 3 — `n8n-nodes-telegram-bridge/`**: a small n8n community
  node with one operation, **Send Message**, that calls the bridge's
  `POST /send` to reply on Telegram.

## Component 1: the Python bridge

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set BOT_TOKEN (from @BotFather), and N8N_WEBHOOK_URL if not default
```

### Run

```bash
python -m telegram_bridge
```

This starts, in one process:

- the long-polling loop, listening for text messages, photos, and
  documents, and
- the local API on `http://127.0.0.1:8811`.

### What gets forwarded to n8n

On every incoming message, the bridge POSTs JSON to `N8N_WEBHOOK_URL`
(default `http://localhost:5678/webhook/telegram-in`):

```json
{
  "chat_id": 123456789,
  "message_id": 42,
  "date": "2026-08-30T12:00:00+00:00",
  "from": { "id": 111, "username": "alice", "first_name": "Alice", "last_name": null },
  "text": "hello",
  "caption": null,
  "file_path": null,
  "file_type": null
}
```

Photos and documents are downloaded to `./incoming/` first (see
`INCOMING_DIR` in `.env`); `file_path` then points at the local file and
`file_type` is `"photo"` or `"document"`.

If n8n is unreachable, the POST is retried up to 3 times with exponential
backoff. A failure after all retries is logged to stdout — it never
crashes the polling loop, so the bridge keeps receiving messages either
way.

### Sending messages back

`POST http://127.0.0.1:8811/send` with either:

```json
{ "chat_id": 123456789, "text": "hi there" }
```

or

```json
{ "chat_id": 123456789, "photo_path": "/opt/telegram-bridge/incoming/some.jpg", "caption": "check this out" }
```

`GET http://127.0.0.1:8811/health` returns `{"status": "ok"}`.

### Running continuously (systemd)

```bash
sudo cp telegram-bridge.service /etc/systemd/system/
sudo mkdir -p /opt/telegram-bridge
sudo cp -r telegram_bridge .env requirements.txt /opt/telegram-bridge/
cd /opt/telegram-bridge && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bridge.service
sudo systemctl status telegram-bridge.service
```

Adjust `User=`, `WorkingDirectory=`, and `ExecStart=` in
`telegram-bridge.service` to match your actual install path. `Restart=on-failure`
handles crashes; `WantedBy=multi-user.target` handles boot.

## Component 2: n8n receive side

Add a **Webhook** node to your workflow:

- **HTTP Method**: `POST`
- **Path**: `telegram-in` (so the full URL is
  `http://localhost:5678/webhook/telegram-in`, matching `N8N_WEBHOOK_URL`)
- **Respond**: "Immediately" is simplest — the bridge doesn't wait on the
  webhook's response body

That's the entire receive side. The Webhook node's payload `body` is the
JSON shown above.

## Component 3: n8n send side (community node)

See [`n8n-nodes-telegram-bridge/README.md`](n8n-nodes-telegram-bridge/README.md)
for install instructions. In short:

```bash
cd n8n-nodes-telegram-bridge
npm install
npm run build
```

Then install it into n8n (community-nodes UI, `~/.n8n/custom`, or
`N8N_CUSTOM_EXTENSIONS` — all documented in that README).

Add a **Telegram Bridge API** credential pointing at
`http://127.0.0.1:8811` (the default), then use the **Telegram Bridge**
node's **Send Message** operation, wired with a **Chat ID** (typically
`{{$json.chat_id}}` from the incoming Webhook data) and either message
text or a photo path + caption.

## Wiring it into a workflow

```
Webhook (telegram-in)  →  [your logic]  →  Telegram Bridge (Send Message)
```

Example: echo bot workflow —

1. **Webhook** node at `/webhook/telegram-in`.
2. A **Set**/**Function** node building a reply, e.g.
   `You said: {{$json.body.text}}`.
3. **Telegram Bridge** node, Chat ID = `{{$json.body.chat_id}}`, Message
   Text = the value from step 2.

## Testing end-to-end

1. Start the bridge: `python -m telegram_bridge`.
2. Start n8n with the Webhook → Telegram Bridge workflow above, active.
3. Open Telegram, find your bot (the one behind `BOT_TOKEN`), and send it
   a text message.
4. Watch the bridge's stdout log — you should see it forward the message
   to n8n.
5. In n8n, check the workflow's execution list for a new run triggered by
   the Webhook node, carrying your message in `body`.
6. If your workflow replies, you should get a message back in Telegram
   within a second or two.
7. Send a photo to the bot and confirm `incoming/` gets a new file and the
   webhook payload's `file_path`/`file_type` are populated.

`curl http://127.0.0.1:8811/health` at any point to confirm the bridge's
API is up.

## Constraints this design holds to

- No public inbound ports anywhere — the bridge binds `127.0.0.1` only,
  never `0.0.0.0`.
- Fully async Python: the polling loop and the FastAPI server share one
  event loop (`asyncio.gather`), no blocking calls.
- Single bot token, single chat use case — no multi-tenant routing.
- Python 3.11+, Node 18+ for the n8n node build.

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
  ├─ long-polling loop ──POST──▶ n8n "Telegram Bridge Trigger" node (http://localhost:5678/webhook/telegram-in)
  └─ FastAPI on 127.0.0.1:8811 ◀──POST── n8n "Telegram Bridge" node (Send Message / Photo / Document / Edit)
```

- **Component 1 — `telegram_bridge/`**: the Python polling service. Runs
  the Telegram long-polling loop and a small FastAPI app in one process
  (`asyncio.gather`), fully async.
- **Component 2 — n8n receive side**: the **Telegram Bridge Trigger**
  community node, listening at `/webhook/telegram-in`. It's a thin
  webhook-style trigger — plain localhost HTTP between the bridge and
  n8n, so n8n's public-HTTPS requirement for Telegram never applies
  here, because it's the *bridge*, not n8n, that talks to Telegram.
  (n8n's built-in **Webhook** node works too, as a fallback that needs
  no extra install — see below — but its output is nested under `body`
  instead of matching the native Telegram Trigger node's shape.)
- **Component 3 — `n8n-nodes-telegram-bridge/`**: an n8n community node
  package with both the trigger above and a **Telegram Bridge** node
  mirroring the built-in Telegram node's send-side operations (Send
  Message, Send Photo, Send Document, Edit Message Text — with parse
  mode, reply threading, and inline keyboards) that calls the bridge's
  `POST /send`.

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

On every incoming message, the bridge POSTs the **raw Telegram Bot API
`Update` object** to `N8N_WEBHOOK_URL` (default
`http://localhost:5678/webhook/telegram-in`) — the exact same shape n8n's
built-in Telegram Trigger node hands a workflow as `$json.body` when
Telegram calls its webhook. That means expressions written against the
native node (`{{$json.body.message.chat.id}}`,
`{{$json.body.message.from.username}}`, `{{$json.body.message.text}}`,
`{{$json.body.message.photo}}`, …) work unmodified here:

```json
{
  "update_id": 123456,
  "message": {
    "message_id": 42,
    "date": 1788055227,
    "chat": { "id": 123456789, "type": "private", "first_name": "Alice" },
    "from": { "id": 111, "username": "alice", "first_name": "Alice", "is_bot": false },
    "text": "hello"
  },
  "bridge": { "file_path": null, "file_type": null }
}
```

The one addition on top of Telegram's native shape is `bridge`: Telegram's
`message.photo`/`message.document` only ever carry a `file_id`, never a
path on disk, so for photos and documents the bridge downloads the
attachment to `./incoming/` (see `INCOMING_DIR` in `.env`) and reports
`bridge.file_path`/`bridge.file_type` (`"photo"` or `"document"`)
alongside the untouched native `message` object.

If n8n is unreachable, the POST is retried up to 3 times with exponential
backoff. A failure after all retries is logged to stdout — it never
crashes the polling loop, so the bridge keeps receiving messages either
way.

### Sending messages back

`POST http://127.0.0.1:8811/send`, mirroring the built-in Telegram node's
operations via an `operation` field (default `sendMessage`):

```json
{ "operation": "sendMessage", "chat_id": 123456789, "text": "hi there" }
```

```json
{ "operation": "sendPhoto", "chat_id": 123456789, "photo_path": "/opt/telegram-bridge/incoming/some.jpg", "caption": "check this out" }
```

```json
{ "operation": "sendDocument", "chat_id": 123456789, "document_path": "/opt/telegram-bridge/incoming/report.pdf" }
```

```json
{ "operation": "editMessageText", "chat_id": 123456789, "message_id": 42, "text": "updated text" }
```

All operations accept the optional fields the native node also exposes:
`parse_mode` (`"Markdown"` / `"MarkdownV2"` / `"HTML"`),
`disable_notification`, `reply_to_message_id`, and `reply_markup` (a
Telegram inline-keyboard object, e.g.
`{"inline_keyboard": [[{"text": "Yes", "callback_data": "yes"}]]}`).

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

Add a **Telegram Bridge Trigger** node to your workflow (from the same
community package as Component 3 — see its install instructions below):

- **Path**: `telegram-in` (so the full URL is
  `http://localhost:5678/webhook/telegram-in`, matching `N8N_WEBHOOK_URL`)

That's the entire receive side. Its output **is** the raw Telegram
`Update` object shown above, unwrapped — `{{$json.message.chat.id}}`,
`{{$json.message.text}}`, `{{$json.bridge.file_path}}`, etc. — identical
to what n8n's native Telegram Trigger node would have delivered.

**Alternative, no install required:** n8n's built-in **Webhook** node
(`POST`, path `telegram-in`, Respond "Immediately") works exactly the
same way, except the payload lands under `body`
(`{{$json.body.message.chat.id}}`) instead of at the top level, since
that's how the generic Webhook node wraps requests.

## Component 3: n8n send side (community node)

See [`n8n-nodes-telegram-bridge/README.md`](n8n-nodes-telegram-bridge/README.md)
for install instructions. In short:

```bash
cd n8n-nodes-telegram-bridge
npm install
npm run build
```

Then install it into n8n (community-nodes UI, `~/.n8n/custom`, or
`N8N_CUSTOM_EXTENSIONS` — all documented in that README). This gets you
both nodes, **Telegram Bridge Trigger** and **Telegram Bridge**, in the
node picker.

Add a **Telegram Bridge API** credential pointing at
`http://127.0.0.1:8811` (the default), then use the **Telegram Bridge**
node with a **Chat ID** (typically `{{$json.message.chat.id}}` from the
trigger) and whichever operation you need — Send Message, Send Photo,
Send Document, or Edit Message Text — with Parse Mode, Reply To Message
ID, and Reply Markup (inline keyboard) available under **Additional
Fields**.

## Wiring it into a workflow

```
Telegram Bridge Trigger (telegram-in)  →  [your logic]  →  Telegram Bridge (Send Message)
```

Example: echo bot workflow —

1. **Telegram Bridge Trigger** node, path `telegram-in`.
2. A **Set**/**Function** node building a reply, e.g.
   `You said: {{$json.message.text}}`.
3. **Telegram Bridge** node, operation **Send Message**, Chat ID =
   `{{$json.message.chat.id}}`, Text = the value from step 2.

## Testing end-to-end

1. Start the bridge: `python -m telegram_bridge`.
2. Start n8n with the Trigger → Telegram Bridge workflow above, active.
3. Open Telegram, find your bot (the one behind `BOT_TOKEN`), and send it
   a text message.
4. Watch the bridge's stdout log — you should see it forward the message
   to n8n.
5. In n8n, check the workflow's execution list for a new run triggered by
   the Telegram Bridge Trigger node, carrying the raw Telegram `Update`.
6. If your workflow replies, you should get a message back in Telegram
   within a second or two.
7. Send a photo to the bot and confirm `incoming/` gets a new file and the
   trigger's `bridge.file_path`/`bridge.file_type` are populated.

`curl http://127.0.0.1:8811/health` at any point to confirm the bridge's
API is up.

## Constraints this design holds to

- No public inbound ports anywhere — the bridge binds `127.0.0.1` only,
  never `0.0.0.0`.
- Fully async Python: the polling loop and the FastAPI server share one
  event loop (`asyncio.gather`), no blocking calls.
- Single bot token, single chat use case — no multi-tenant routing.
- Python 3.11+, Node 18+ for the n8n node build.

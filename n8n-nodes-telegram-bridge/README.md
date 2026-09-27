# n8n-nodes-telegram-bridge

An n8n community node package that talks to a locally running
`telegram_bridge` service instead of n8n's built-in Telegram node — see the
[top-level README](../README.md) for why. It provides two node types:

- **Telegram Bridge Trigger** — starts the workflow when the bridge forwards
  a Telegram update. It's a webhook-style trigger (same underlying mechanism
  as n8n's built-in Webhook node), listening at a configurable path
  (default `telegram-in`) for localhost-only POSTs from the bridge — never
  a public HTTPS endpoint. Its output is the raw Telegram Update object,
  unwrapped, matching n8n's built-in **Telegram Trigger** node's shape
  exactly: `{{$json.message.chat.id}}`, `{{$json.message.text}}`, etc.
- **Telegram Bridge** — mirrors the send-side operations n8n's built-in
  Telegram node exposes: **Send Message**, **Send Photo**, **Send
  Document**, **Edit Message Text**, plus Parse Mode, Reply To Message ID,
  Disable Notification, and Reply Markup (inline keyboards) under
  Additional Fields. Every operation calls `POST http://127.0.0.1:8811/send`
  (or whatever base URL your credential points at) on the bridge.

## Install as a community node

### Option A: n8n's Community Nodes UI

1. Build this package first (see below) and publish it to a private/public
   npm registry, or pack it locally: `npm pack`.
2. In n8n, go to **Settings → Community Nodes → Install**, and enter
   `n8n-nodes-telegram-bridge` (or the path/tarball if installing locally).

### Option B: manual install into `~/.n8n/custom`

```bash
cd n8n-nodes-telegram-bridge
npm install
npm run build

mkdir -p ~/.n8n/custom
cd ~/.n8n/custom
npm init -y   # only if this is the first custom node you're adding
npm install /path/to/n8n-nodes-telegram-bridge
```

**Restart n8n.** Both **Telegram Bridge Trigger** and **Telegram Bridge**
should now appear in the node picker. If they don't, see
[Nodes don't appear in the picker](#nodes-dont-appear-in-the-picker).

`~/.n8n/custom` must be the `.n8n` folder of the user that **runs n8n**
(or `$N8N_USER_FOLDER/.n8n/custom` if that's set). Installing it with
`npm install -g` or `npm link` does not work: n8n 2.x no longer loads
custom nodes from the global `node_modules`.

Nodes installed this way are internally namespaced `CUSTOM.<nodeName>`
(e.g. `CUSTOM.telegramBridgeTrigger`) — that prefix is expected and
harmless; it's how n8n labels anything loaded from `~/.n8n/custom` or
`N8N_CUSTOM_EXTENSIONS`, as opposed to a package installed through the
Community Nodes UI (which keeps the real package name).

### Option C: `N8N_CUSTOM_EXTENSIONS`

```bash
cd n8n-nodes-telegram-bridge
npm install
npm run build

# n8n scans this directory recursively for *.node.js files, so pointing
# it at the package folder itself is enough. Separate several with ';'.
export N8N_CUSTOM_EXTENSIONS="/path/to/n8n-nodes-telegram-bridge"
n8n start
```

The variable has to be set in the environment of the n8n **process** —
for a systemd service that's an `Environment=` line in the unit, and for
pm2 it's the ecosystem file, not your interactive shell.

## Credential

Create a **Telegram Bridge API** credential with:

- **Bridge Base URL** — default `http://127.0.0.1:8811`, matching
  `BRIDGE_PORT` in the Python bridge's `.env`.

## Building

```bash
npm install
npm run build   # runs tsc, emits dist/, copies icon.svg
```

## Nodes don't appear in the picker

Run the read-only diagnostic script on the machine where n8n runs, while
n8n is running (use `sudo` if n8n runs as a different user, e.g. a
systemd service):

```bash
bash scripts/diagnose.sh                 # auto-detects the running n8n
bash scripts/diagnose.sh /home/n8nuser   # or name the folder containing .n8n/
```

It prints which folders the running n8n scans, whether the built nodes
are in them, whether the running n8n actually loaded them, and a verdict
listing what to fix. The usual causes are:

- **Installed into the wrong `.n8n`** — n8n runs as another user, under
  `sudo`, or with `N8N_USER_FOLDER`, so it reads a different
  `.n8n/custom` from the one you installed into.
- **Installed globally** (`npm install -g` / `npm link`) — ignored by
  n8n 2.x.
- **n8n not restarted** — a systemd or pm2 service keeps the old
  process until you restart *that* service.
- **`NODES_INCLUDE` is set** — only the listed nodes are loaded; add
  `CUSTOM.telegramBridge` and `CUSTOM.telegramBridgeTrigger`, or unset it.
- **`dist/` missing or stale** — run `npm install && npm run build`.

Where to look once it's loaded: in an empty workflow, search **Telegram
Bridge** — n8n lists the trigger as "Telegram Bridge" (it drops the word
"Trigger" in the trigger list). The send node only shows up when you add
a step *after* a trigger. Hard-refresh the browser tab after restarting
n8n.

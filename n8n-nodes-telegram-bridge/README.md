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
should now appear in the node picker. If you see "Unrecognized node
type" in a workflow, it almost always means one of: the package wasn't
rebuilt (`npm run build` — check `dist/` exists), n8n wasn't restarted
after installing/updating it, or it was installed under a different
directory/name than the one currently configured.

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

# Point this at the PARENT directory of the package, not the package
# folder itself — n8n scans each entry for subfolders that are npm
# packages.
export N8N_CUSTOM_EXTENSIONS="/path/to"
n8n start
```

## Credential

Create a **Telegram Bridge API** credential with:

- **Bridge Base URL** — default `http://127.0.0.1:8811`, matching
  `BRIDGE_PORT` in the Python bridge's `.env`.

## Building

```bash
npm install
npm run build   # runs tsc, emits dist/, copies icon.svg
```

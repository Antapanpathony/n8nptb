# n8n-nodes-telegram-bridge

An n8n community node that sends Telegram messages through a locally running
`telegram_bridge` service instead of n8n's built-in Telegram node — see the
[top-level README](../README.md) for why.

It mirrors the send-side operations n8n's built-in Telegram node exposes —
**Send Message**, **Send Photo**, **Send Document**, **Edit Message
Text** — plus Parse Mode, Reply To Message ID, Disable Notification, and
Reply Markup (inline keyboards) under Additional Fields. Every operation
calls `POST http://127.0.0.1:8811/send` (or whatever base URL your
credential points at) on the bridge.

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

Restart n8n. The **Telegram Bridge** node should now appear in the node
picker.

### Option C: `N8N_CUSTOM_EXTENSIONS`

```bash
cd n8n-nodes-telegram-bridge
npm install
npm run build

export N8N_CUSTOM_EXTENSIONS="/path/to/n8n-nodes-telegram-bridge"
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

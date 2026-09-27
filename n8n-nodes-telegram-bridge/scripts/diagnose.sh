#!/usr/bin/env bash
# Read-only diagnostics for "Telegram Bridge nodes don't show up in n8n".
#
# Run it on the machine where n8n runs, ideally while n8n is running:
#   bash n8n-nodes-telegram-bridge/scripts/diagnose.sh
# If n8n runs as another user (systemd service, pm2 under root, ...), run it
# with sudo so the script can read that process's environment.
#
# Optional: pass the n8n user folder explicitly (the directory that CONTAINS
# .n8n/), e.g.  bash scripts/diagnose.sh /home/n8n
#
# It changes nothing; it only prints what it finds and a verdict at the end.

set -u

PKG_NAME="n8n-nodes-telegram-bridge"
NODE_NAMES="telegramBridge telegramBridgeTrigger"
PKG_DIR="$(cd "$(dirname "$0")/.." && pwd)"

problems=()
section() { printf '\n== %s ==\n' "$1"; }
problem() { problems+=("$1"); printf '  !! %s\n' "$1"; }

section "Tools"
for tool in node npm n8n; do
	if command -v "$tool" >/dev/null 2>&1; then
		printf '  %-5s %s  (%s)\n' "$tool" "$("$tool" --version 2>/dev/null | head -1)" "$(command -v "$tool")"
	else
		printf '  %-5s not on PATH\n' "$tool"
	fi
done

section "Running n8n process"
pid=""
if command -v pgrep >/dev/null 2>&1; then
	pid="$(pgrep -f 'n8n( |$)start|bin/n8n|n8n/bin' | grep -v "^$$\$" | head -1 || true)"
fi
proc_env=""
if [ -n "$pid" ]; then
	echo "  pid:  $pid"
	echo "  user: $(ps -o user= -p "$pid" 2>/dev/null)"
	echo "  cmd:  $(ps -o args= -p "$pid" 2>/dev/null)"
	echo "  started: $(ps -o lstart= -p "$pid" 2>/dev/null)"
	if [ -r "/proc/$pid/environ" ]; then
		proc_env="$(tr '\0' '\n' < "/proc/$pid/environ")"
	else
		# macOS / no /proc: best effort (only works for your own processes).
		proc_env="$(ps eww -o command= -p "$pid" 2>/dev/null | tr ' ' '\n' | grep '=' || true)"
	fi
	[ -z "$proc_env" ] && echo "  (can't read its environment — rerun with sudo)"
else
	echo "  no running n8n process found (start n8n and rerun for a full report)"
fi

env_of() {
	# Value of $1 in the n8n process env, falling back to this shell's env.
	local v
	v="$(printf '%s\n' "$proc_env" | sed -n "s/^$1=//p" | head -1)"
	if [ -z "$v" ] && [ -z "$proc_env" ]; then v="${!1:-}"; fi
	printf '%s' "$v"
}

section "n8n environment (from the running process when possible)"
for var in HOME N8N_USER_FOLDER N8N_CUSTOM_EXTENSIONS NODES_INCLUDE NODES_EXCLUDE; do
	printf '  %-22s %s\n' "$var" "$(env_of "$var")"
done

user_folder="${1:-}"
if [ -z "$user_folder" ]; then
	user_folder="$(env_of N8N_USER_FOLDER)"
	[ -z "$user_folder" ] && user_folder="$(env_of HOME)"
fi
custom_dir="$user_folder/.n8n/custom"
section "Custom node directories n8n will scan"
echo "  user folder: $user_folder"
echo "  custom dir:  $custom_dir"

scan_dirs=("$custom_dir")
ext="$(env_of N8N_CUSTOM_EXTENSIONS)"
if [ -n "$ext" ]; then
	IFS=';' read -r -a ext_dirs <<< "$ext"
	scan_dirs+=("${ext_dirs[@]}")
fi

found_any=0
for dir in "${scan_dirs[@]}"; do
	[ -z "$dir" ] && continue
	echo "  -- $dir"
	if [ ! -d "$dir" ]; then
		echo "     (does not exist)"
		continue
	fi
	hits="$(find -L "$dir" -name '*.node.js' -path '*TelegramBridge*' -not -path '*/node_modules/*/node_modules/*' 2>/dev/null)"
	if [ -n "$hits" ]; then
		found_any=1
		printf '%s\n' "$hits" | sed 's/^/     found: /'
	else
		echo "     no TelegramBridge *.node.js files here"
	fi
	if [ -L "$dir/node_modules/$PKG_NAME" ]; then
		echo "     $PKG_NAME is a symlink -> $(readlink "$dir/node_modules/$PKG_NAME")"
	fi
done
if [ "$found_any" = 0 ]; then
	problem "n8n's custom directories contain no built Telegram Bridge nodes. Install the package into $custom_dir (see README, Option B) or set N8N_CUSTOM_EXTENSIONS for the n8n process."
fi

section "Global npm install (ignored by n8n 2.x)"
if npm ls -g --depth=0 "$PKG_NAME" 2>/dev/null | grep -q "$PKG_NAME"; then
	echo "  $PKG_NAME is installed globally"
	[ "$found_any" = 0 ] && problem "The package is only installed globally (npm install -g / npm link). n8n 2.x no longer loads custom nodes from the global node_modules."
else
	echo "  not installed globally"
fi

section "NODES_INCLUDE / NODES_EXCLUDE"
inc="$(env_of NODES_INCLUDE)"
exc="$(env_of NODES_EXCLUDE)"
for n in $NODE_NAMES; do
	if [ -n "$inc" ] && ! printf '%s' "$inc" | grep -q "$n"; then
		problem "NODES_INCLUDE is set and does not list CUSTOM.$n, so n8n hides it."
	fi
	if printf '%s' "$exc" | grep -q "$n"; then
		problem "NODES_EXCLUDE lists $n, so n8n hides it."
	fi
done
[ -z "$inc" ] && echo "  NODES_INCLUDE not set (good)"

section "Repo build ($PKG_DIR)"
if [ -f "$PKG_DIR/dist/index.js" ]; then
	(cd "$PKG_DIR" && node -e "
		const m = require('./dist');
		for (const k of ['TelegramBridge', 'TelegramBridgeTrigger', 'TelegramBridgeApi']) {
			const i = new m[k]();
			console.log('  loads OK:', k, '->', (i.description || i).name);
		}" 2>&1) || problem "dist/ exists but fails to load — rebuild with: npm install && npm run build"
else
	problem "dist/ is missing in $PKG_DIR — run: npm install && npm run build"
fi

section "What the running n8n actually loaded"
types="$user_folder/.cache/n8n/public/types/nodes.json"
if [ -f "$types" ]; then
	echo "  $types (written $(date -r "$types" 2>/dev/null))"
	for n in $NODE_NAMES; do
		if grep -q "\"CUSTOM.$n\"\|\"$PKG_NAME.$n\"" "$types"; then
			echo "  loaded: $n"
		else
			problem "The running n8n did NOT load $n (not in $types)."
		fi
	done
	if [ -n "$pid" ] && [ "$found_any" = 1 ] && [ -f "$custom_dir/node_modules/$PKG_NAME/dist/index.js" ] \
		&& [ "$custom_dir/node_modules/$PKG_NAME/dist/index.js" -nt "$types" ]; then
		problem "The package was rebuilt/installed after n8n last started. Restart n8n (the actual service: systemctl restart / pm2 restart / Ctrl+C and start again)."
	fi
else
	echo "  no types cache at $types"
	[ -n "$pid" ] && problem "n8n is running but not with user folder $user_folder — it's reading a different .n8n folder than the one checked here. Rerun with sudo, or pass the right folder: bash scripts/diagnose.sh /path/containing/.n8n"
fi

section "Verdict"
if [ "${#problems[@]}" -eq 0 ]; then
	echo "  No problems found. The nodes should be in the picker:"
	echo "  - empty workflow -> search 'Telegram Bridge' -> the trigger shows as 'Telegram Bridge' (n8n drops the word 'Trigger')"
	echo "  - after a trigger, click + -> search 'Telegram Bridge' for the send node"
	echo "  Hard-refresh the browser tab (Ctrl+Shift+R) if n8n was restarted while it was open."
else
	for p in "${problems[@]}"; do echo "  - $p"; done
fi

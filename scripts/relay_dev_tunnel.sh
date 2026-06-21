#!/usr/bin/env bash
#
# Local inbound-email loop for the inquiry relay (shared-route mode).
#
# The Mailgun plan allows only ONE inbound Route, and production owns it. So
# instead of creating a second route, this script temporarily edits the existing
# route to ALSO forward replies to a local cloudflared tunnel, then restores the
# route to its original actions when you stop the script (Ctrl-C).
#
# While running:
#   * prod replies still reach production (unchanged forward) AND are copied to
#     your local server, which drops unknown thread tokens — harmless but note
#     that real reply bodies transit your machine during the session.
#   * replies to your local test inquiries relay locally.
#
# Usage:  make relay-tunnel        (or)   bash scripts/relay_dev_tunnel.sh
# Run the dev server separately:    make run
#
set -euo pipefail

PORT="${RELAY_TUNNEL_PORT:-8000}"
WEBHOOK_PATH="/relay/mailgun/inbound"
RECIPIENT="marketplace@relay.heavyuse.us"   # the address the shared Route matches

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

# --- read the Mailgun API key out of .env (format:  MAILGUN_KEY = 'value') ---
MAILGUN_KEY="$(grep -E '^[[:space:]]*MAILGUN_KEY[[:space:]]*=' "$ENV_FILE" \
  | head -1 | sed -E "s/^[^=]*=[[:space:]]*//; s/^['\"]//; s/['\"][[:space:]]*$//")"
if [[ -z "${MAILGUN_KEY:-}" ]]; then
  echo "ERROR: MAILGUN_KEY not found in $ENV_FILE" >&2
  exit 1
fi
API="https://api.mailgun.net/v3/routes"

# --- locate the shared Route and capture its original config ---
ROUTES_JSON="$(curl -s --user "api:$MAILGUN_KEY" "$API?limit=1000")"
ROUTE_ID="$(echo "$ROUTES_JSON" | python3 -c "
import sys, json
r = [r for r in json.load(sys.stdin).get('items', []) if '$RECIPIENT' in r.get('expression','')]
print(r[0]['id'] if r else '')")"
if [[ -z "$ROUTE_ID" ]]; then
  echo "ERROR: no Mailgun route matching $RECIPIENT was found." >&2
  exit 1
fi

ROUTE_PRIORITY="$(echo "$ROUTES_JSON" | python3 -c "
import sys, json
r = next(r for r in json.load(sys.stdin)['items'] if r['id']=='$ROUTE_ID'); print(r.get('priority',0))")"
ROUTE_EXPR="$(echo "$ROUTES_JSON" | python3 -c "
import sys, json
r = next(r for r in json.load(sys.stdin)['items'] if r['id']=='$ROUTE_ID'); print(r['expression'])")"
ROUTE_DESC="$(echo "$ROUTES_JSON" | python3 -c "
import sys, json
r = next(r for r in json.load(sys.stdin)['items'] if r['id']=='$ROUTE_ID'); print(r.get('description',''))")"
# (read into an array the bash-3.2 way; macOS ships no `mapfile`)
ORIG_ACTIONS=()
while IFS= read -r _line; do
  ORIG_ACTIONS+=( "$_line" )
done < <(echo "$ROUTES_JSON" | python3 -c "
import sys, json
r = next(r for r in json.load(sys.stdin)['items'] if r['id']=='$ROUTE_ID')
print('\n'.join(r['actions']))")
if [[ ${#ORIG_ACTIONS[@]} -eq 0 ]]; then
  echo "ERROR: could not read original actions for route $ROUTE_ID." >&2
  exit 1
fi

echo "Found shared route $ROUTE_ID"
echo "  original actions: ${ORIG_ACTIONS[*]}"

# build curl '-F action=...' args from an array of action strings
action_args() { local a; ARGS=(); for a in "$@"; do ARGS+=( -F "action=$a" ); done; }

TUNNEL_PID=""
RESTORED=""

restore_route() {
  [[ -n "$RESTORED" ]] && return; RESTORED=1
  # never PUT an empty action set -- that would blank the live route
  if [[ ${#ORIG_ACTIONS[@]} -eq 0 ]]; then
    echo "WARNING: no saved actions to restore; leaving route $ROUTE_ID untouched." >&2
    return
  fi
  echo "Restoring route $ROUTE_ID to original actions ..."
  action_args "${ORIG_ACTIONS[@]}"
  curl -s --user "api:$MAILGUN_KEY" -X PUT "$API/$ROUTE_ID" \
    -F priority="$ROUTE_PRIORITY" -F description="$ROUTE_DESC" \
    -F expression="$ROUTE_EXPR" "${ARGS[@]}" >/dev/null || \
    echo "WARNING: restore failed -- check route $ROUTE_ID in the Mailgun dashboard!" >&2
}

cleanup() {
  echo
  restore_route
  if [[ -n "$TUNNEL_PID" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
    kill "$TUNNEL_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# --- start the cloudflared quick tunnel and capture its public URL ---
LOG="$(mktemp -t relay_tunnel.XXXXXX)"
# --protocol http2 forces the edge connection over TCP instead of the default
# QUIC/UDP (port 7844), which many VPNs block. Override with RELAY_TUNNEL_PROTOCOL.
TUNNEL_PROTOCOL="${RELAY_TUNNEL_PROTOCOL:-http2}"
echo "Starting cloudflared quick tunnel (protocol=$TUNNEL_PROTOCOL) -> http://localhost:$PORT ..."
cloudflared tunnel --no-autoupdate --protocol "$TUNNEL_PROTOCOL" --url "http://localhost:$PORT" >"$LOG" 2>&1 &
TUNNEL_PID=$!

TUNNEL_URL=""
for _ in $(seq 1 30); do
  TUNNEL_URL="$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [[ -n "$TUNNEL_URL" ]] && break
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    echo "ERROR: cloudflared exited early. Log:" >&2; cat "$LOG" >&2; exit 1
  fi
  sleep 1
done
if [[ -z "$TUNNEL_URL" ]]; then
  echo "ERROR: could not determine tunnel URL. Log:" >&2; cat "$LOG" >&2; exit 1
fi
echo "Tunnel URL: $TUNNEL_URL"

# wait for the edge to actually register the connection before probing it
echo "Waiting for tunnel to register with the Cloudflare edge ..."
for _ in $(seq 1 40); do
  grep -q "Registered tunnel connection" "$LOG" && break
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    echo "ERROR: cloudflared exited early. Log:" >&2; cat "$LOG" >&2; exit 1
  fi
  sleep 1
done

# --- build the new action set: original actions + a forward() to the tunnel
# (stop() kept last). The local server must be running (make run) so the tunnel
# proxies to something real -- Mailgun probes the URL before accepting it.
FORWARD_URL="${TUNNEL_URL}${WEBHOOK_PATH}"
NEW_ACTIONS=()
HAS_STOP=""
for a in "${ORIG_ACTIONS[@]}"; do
  [[ "$a" == "stop()" ]] && { HAS_STOP=1; continue; }
  NEW_ACTIONS+=( "$a" )
done
NEW_ACTIONS+=( "forward(\"$FORWARD_URL\")" )
[[ -n "$HAS_STOP" ]] && NEW_ACTIONS+=( "stop()" )
action_args "${NEW_ACTIONS[@]}"

# Mailgun validates that the forward URL is publicly reachable when we save the
# route -- that probe is the real health check (this machine, on a VPN, can't be
# trusted to reach the tunnel hostname). Retry while the edge is still
# propagating ("must be publicly accessible").
echo "Registering tunnel with Mailgun (it probes the URL; retrying while it propagates) ..."
UPDATE_OK=""
for attempt in $(seq 1 12); do
  UPDATE_RESP="$(curl -s --user "api:$MAILGUN_KEY" -X PUT "$API/$ROUTE_ID" \
    -F priority="$ROUTE_PRIORITY" -F description="$ROUTE_DESC" \
    -F expression="$ROUTE_EXPR" "${ARGS[@]}")"
  UPDATE_OK="$(printf '%s' "$UPDATE_RESP" | python3 -c "import sys,json; print('ok' if 'updated' in json.load(sys.stdin).get('message','').lower() else '')" 2>/dev/null || true)"
  [[ -n "$UPDATE_OK" ]] && break
  if printf '%s' "$UPDATE_RESP" | grep -q "publicly accessible"; then
    echo "  attempt $attempt: edge not ready yet, retrying in 5s ..."
    sleep 5
    continue
  fi
  break  # a different error -- stop and report it
done
if [[ -z "$UPDATE_OK" ]]; then
  echo "ERROR: failed to update Mailgun route. Last response:" >&2
  echo "$UPDATE_RESP" >&2
  echo "  - Is the dev server running?  make run" >&2
  echo "  - If it keeps saying 'publicly accessible', disconnect the VPN and retry." >&2
  exit 1
fi

cat <<EOF

  Dev inbound relay is live (shared route).
    reply-to address : $RECIPIENT   (INQUIRY_RELAY_EMAIL in .env)
    now forwards to   : ${ORIG_ACTIONS[*]} + forward("$FORWARD_URL")
    route id          : $ROUTE_ID

  Make sure the dev server is running (make run) on port $PORT.
  Send an inquiry, reply to the email, watch it relay locally.
  Press Ctrl-C to restore the route and stop the tunnel.

EOF

wait "$TUNNEL_PID"

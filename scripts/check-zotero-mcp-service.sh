#!/usr/bin/env bash

set -euo pipefail

PORT="${ZOTERO_MCP_PORT:-23120}"
HOST="${ZOTERO_MCP_HOST:-127.0.0.1}"
ENDPOINT="${ZOTERO_MCP_ENDPOINT:-http://${HOST}:${PORT}/mcp}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required" >&2
  exit 2
fi

if ! lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "FAIL: no process is listening on TCP ${PORT}" >&2
  exit 1
fi

REQUEST_BODY="$(mktemp)"
RESPONSE_BODY="$(mktemp)"
trap 'rm -f "${REQUEST_BODY}" "${RESPONSE_BODY}"' EXIT

cat >"${REQUEST_BODY}" <<'EOF'
{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"check-zotero-mcp-service","version":"1.0"}}}
EOF

HTTP_CODE="$(
  curl --noproxy '*' -sS \
    -o "${RESPONSE_BODY}" \
    -w '%{http_code}' \
    -m 10 \
    -X POST "${ENDPOINT}" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    --data @"${REQUEST_BODY}"
)"

if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "FAIL: endpoint ${ENDPOINT} returned HTTP ${HTTP_CODE}" >&2
  sed -n '1,40p' "${RESPONSE_BODY}" >&2 || true
  exit 1
fi

echo "PASS: endpoint reachable at ${ENDPOINT}"
sed -n '1,20p' "${RESPONSE_BODY}" || true

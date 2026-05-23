#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_SRC_DIR="${REPO_ROOT}/mcp-service/src"
BASE_DIR="${ZOTERO_MCP_BASE_DIR:-${REPO_ROOT}/mcp-service-data}"
RUNNER="${ZOTERO_MCP_RUNNER:-stub}"
PORT="${ZOTERO_MCP_PORT:-23120}"
HOST="${ZOTERO_MCP_HOST:-127.0.0.1}"
USER_HOME="${HOME:-$(dscl . -read "/Users/$(id -un)" NFSHomeDirectory | awk '{print $2}')}"

find_python() {
  local candidates=()

  if [[ -n "${ZOTERO_MCP_PYTHON:-}" ]]; then
    candidates+=("${ZOTERO_MCP_PYTHON}")
  fi

  candidates+=(
    "${REPO_ROOT}/mcp-service/.venv/bin/python"
    "${USER_HOME}/.local/share/mise/installs/python/3.12/bin/python3"
    "/opt/homebrew/bin/python3"
  )

  if command -v python3 >/dev/null 2>&1; then
    candidates+=("$(command -v python3)")
  fi

  local candidate
  for candidate in "${candidates[@]}"; do
    [[ -x "${candidate}" ]] || continue
    if PYTHONPATH="${SERVICE_SRC_DIR}" "${candidate}" - <<'PY' >/dev/null 2>&1
import importlib
mods = ("mcp", "pypdf", "zotero_mcp_enhanced_service")
for name in mods:
    importlib.import_module(name)
PY
    then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

PYTHON_BIN="$(find_python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  cat >&2 <<EOF
ERROR: no usable Python interpreter found for zotero-mcp-enhanced-service.

Checked:
- ZOTERO_MCP_PYTHON
- ${REPO_ROOT}/mcp-service/.venv/bin/python
- ${USER_HOME}/.local/share/mise/installs/python/3.12/bin/python3
- /opt/homebrew/bin/python3
- python3 on PATH

Required imports:
- mcp
- pypdf
- zotero_mcp_enhanced_service
EOF
  exit 1
fi

mkdir -p "${BASE_DIR}"
export PYTHONPATH="${SERVICE_SRC_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
export MCP_HTTP_PORT="${PORT}"

echo "Starting zotero-mcp-enhanced-service"
echo "  repo_root: ${REPO_ROOT}"
echo "  python: ${PYTHON_BIN}"
echo "  base_dir: ${BASE_DIR}"
echo "  runner: ${RUNNER}"
echo "  endpoint: http://${HOST}:${PORT}/mcp"

exec "${PYTHON_BIN}" -m zotero_mcp_enhanced_service \
  --base-dir "${BASE_DIR}" \
  --runner "${RUNNER}" \
  --transport streamable-http \
  --port "${PORT}"

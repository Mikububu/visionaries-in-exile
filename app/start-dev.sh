#!/bin/bash
# Force Homebrew Node so Vite's native bindings (rollup/esbuild) load without
# the Codex-bundled hardened-runtime blocking cross-Team-ID .node modules.
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
export ROLLUP_NATIVE=false
cd "$(dirname "$0")"
exec /opt/homebrew/opt/node@22/bin/npm run dev

#!/bin/bash
# SessionStart hook for Claude Code on the web: make `npm run qa` work first try.
# The QA suites need node_modules (playwright) and a Chromium binary; build.py and
# tools/mkqa.py use only the Python standard library.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# playwright (the only npm dependency); npm install is idempotent and its result is cached with the container
if [ ! -d node_modules/playwright ]; then
  npm install --no-audit --no-fund
fi

# Chromium: the container ships one under PLAYWRIGHT_BROWSERS_PATH; the suites read CHROMIUM_PATH.
# Only download a browser when none of the known locations has one.
CHROME=""
for c in "${CHROMIUM_PATH:-}" "${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}/chromium" /opt/pw-browsers/chromium; do
  if [ -n "$c" ] && [ -x "$c" ]; then CHROME="$c"; break; fi
done
if [ -z "$CHROME" ]; then
  npx playwright install chromium
  CHROME="$(node -e "console.log(require('playwright').chromium.executablePath())")"
fi
echo "export CHROMIUM_PATH=\"$CHROME\"" >> "${CLAUDE_ENV_FILE:-/dev/null}"

# the QA page is generated from index.html and is git-ignored: build it once so a suite can run alone
python3 tools/mkqa.py >/dev/null

echo "session-start: playwright ready, CHROMIUM_PATH=$CHROME"

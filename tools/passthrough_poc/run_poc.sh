#!/usr/bin/env bash
# tools/passthrough_poc/run_poc.sh
#
# Launches the independent R60 passthrough proof-of-concept.
# The PoC must NOT be folded back into candidate B main interaction code
# until real Mac evidence is collected.
set -e
DST="$(cd "$(dirname "$0")/../.." && git rev-parse --show-toplevel)"
cd "$DST/candidates/candidate_b_electronpixir"
echo "[run_poc] launching independent passthrough PoC for 35s..."
./node_modules/.bin/electron "$DST/tools/passthrough_poc/main.js" > /tmp/passthrough_poc.log 2>&1 &
P=$!
sleep 35
[ -d /proc/$P ] && kill -9 $P 2>/dev/null
echo "--- PoC log ---"
cat /tmp/passthrough_poc.log | head -30
echo ""
echo "Note: This PoC must be re-run on a real Mac mini with a human user"
echo "clicking the yellow ball center and the transparent corner, then"
echo="confirming the underlay Probe window's counter increments."

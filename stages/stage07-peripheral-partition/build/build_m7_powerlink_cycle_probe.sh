#!/usr/bin/env bash
# P3j complete fresh source build + real guard/owner and cumulative regressions.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
bash "$stage/build/build_m7_powerlink_nmt.sh"
bash "$stage/tests/run_powerlink_cycle_probe_native.sh"
bash "$stage/tests/run_powerlink_cycle_native.sh"
bash "$stage/tests/run_powerlink_nmt_probe_native.sh"

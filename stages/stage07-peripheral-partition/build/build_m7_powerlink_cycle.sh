#!/usr/bin/env bash
# P3i software only. Fresh complete native+AArch64 core/port build, no candidate.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
bash "$stage/build/build_m7_powerlink_nmt.sh"
POWERLINK_BUILD_ROOT="${POWERLINK_BUILD_ROOT:?}" bash "$stage/tests/run_powerlink_cycle_native.sh"

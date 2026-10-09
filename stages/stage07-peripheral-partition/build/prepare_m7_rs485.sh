#!/usr/bin/env bash
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly uni=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-rs485}
# Reuse default-off UART test hooks/CRC from 0005, not CAN FD patch 0004.
UNIPROTON_ROOT="${uni}" bash "${stage_root}/build/prepare_m7_rs232.sh"
git -C "${uni}" apply --check "${stage_root}/source/patches/uniproton/0006-rk3572-rs485-test-hook.patch"
git -C "${uni}" apply "${stage_root}/source/patches/uniproton/0006-rk3572-rs485-test-hook.patch"
install -m 0644 "${stage_root}/source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_rs485_test.c" \
    "${uni}/demos/rk3572_mica/apps/openamp/rk3572_rs485_test.c"
echo "Prepared independent RS485 source: ${uni}"

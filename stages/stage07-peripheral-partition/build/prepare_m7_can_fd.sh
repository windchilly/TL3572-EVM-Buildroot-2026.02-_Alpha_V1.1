#!/usr/bin/env bash
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly uni=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-can-fd}
readonly app_dir="${uni}/demos/rk3572_mica/apps/openamp"
M7_CAN_IRQ_TEST=ON UNIPROTON_ROOT="${uni}" bash "${stage_root}/build/prepare_m7_uniproton.sh"
git -C "${uni}" apply --check "${stage_root}/source/patches/uniproton/0004-rk3572-can-fd-test-hook.patch"
git -C "${uni}" apply "${stage_root}/source/patches/uniproton/0004-rk3572-can-fd-test-hook.patch"
for source in rk3572_can_fd_test.c rk3572_can_fd_codec.h; do
    install -m 0644 "${stage_root}/source/overlay/uniproton/demos/rk3572_mica/apps/openamp/${source}" "${app_dir}/${source}"
done
echo "Prepared independent CAN FD source: ${uni}"

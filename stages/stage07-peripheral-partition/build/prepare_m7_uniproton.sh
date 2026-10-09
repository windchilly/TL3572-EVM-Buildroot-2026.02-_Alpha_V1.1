#!/usr/bin/env bash
set -euo pipefail

readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly m6_root=${M6_UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton}
readonly m7_root=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7}
readonly patch_dir="${stage_root}/source/patches/uniproton"
readonly overlay_file="${stage_root}/source/overlay/uniproton/demos/rk3572_mica/bsp/print.c"
readonly can_overlay_file="${stage_root}/source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_can_test.c"

if [[ ! -d "${m6_root}/demos/rk3572_mica" ]]; then
    echo "M6 UniProton baseline missing: ${m6_root}" >&2
    exit 1
fi
if [[ -e "${m7_root}" ]]; then
    echo "Destination already exists; refusing to overwrite: ${m7_root}" >&2
    exit 1
fi

cp -a "${m6_root}" "${m7_root}"
for patch_file in \
    "${patch_dir}/0001-dual-boot-log-and-uart0-isolation.patch" \
    "${patch_dir}/0002-rk3572-can-direct-test-hook.patch"
do
    git -C "${m7_root}" apply --check "${patch_file}"
    git -C "${m7_root}" apply "${patch_file}"
done
if [[ "${M7_CAN_IRQ_TEST:-OFF}" == ON ]]; then
    git -C "${m7_root}" apply --check "${patch_dir}/0003-rk3572-can-irq-test-hook.patch"
    git -C "${m7_root}" apply "${patch_dir}/0003-rk3572-can-irq-test-hook.patch"
fi
install -m 0644 "${overlay_file}" "${m7_root}/demos/rk3572_mica/bsp/print.c"
install -m 0644 "${can_overlay_file}" \
    "${m7_root}/demos/rk3572_mica/apps/openamp/rk3572_can_test.c"
install -m 0644 "${stage_root}/source/overlay/uniproton/demos/rk3572_mica/apps/openamp/rk3572_can_irq_test.c" \
    "${m7_root}/demos/rk3572_mica/apps/openamp/rk3572_can_irq_test.c"
echo "Prepared M7 source: ${m7_root}"

#!/usr/bin/env bash
set -euo pipefail

readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly m6_root=${M6_UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton}
readonly m7_root=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7}
readonly patch_file="${stage_root}/source/patches/uniproton/0001-dual-boot-log-and-uart0-isolation.patch"
readonly overlay_file="${stage_root}/source/overlay/uniproton/demos/rk3572_mica/bsp/print.c"

if [[ ! -d "${m6_root}/demos/rk3572_mica" ]]; then
    echo "M6 UniProton baseline missing: ${m6_root}" >&2
    exit 1
fi
if [[ -e "${m7_root}" ]]; then
    echo "Destination already exists; refusing to overwrite: ${m7_root}" >&2
    exit 1
fi

cp -a "${m6_root}" "${m7_root}"
git -C "${m7_root}" apply --check "${patch_file}"
git -C "${m7_root}" apply "${patch_file}"
install -m 0644 "${overlay_file}" "${m7_root}/demos/rk3572_mica/bsp/print.c"
echo "Prepared M7 source: ${m7_root}"

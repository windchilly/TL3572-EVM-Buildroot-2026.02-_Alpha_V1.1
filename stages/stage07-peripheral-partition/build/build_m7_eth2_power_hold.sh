#!/usr/bin/env bash
set -euo pipefail
stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
project=${TL3572_PROJECT:-/home/openeuler/build/tl3572-2oo3}
kernel_src=${TL3572_KERNEL_SRC:-$project/kernel-src-pristine}
kernel_build=${TL3572_KERNEL_BUILD:-$project/build-kernel}
module_build=${M7_ETH2_MODULE_BUILD_DIR:-$project/build-m7-eth2-power-hold}
test -s "$kernel_build/Module.symvers"
test -s "$kernel_build/include/generated/utsrelease.h"
grep -q '"6.12.69-gf1b67c293213"' "$kernel_build/include/generated/utsrelease.h"
# /repo is read-only in the clean reproduction container. Never write kbuild
# outputs beside the checked-in module sources.
mkdir -p "$module_build"
install -m 0644 "$stage/source/host/eth2-power-hold/Makefile" "$module_build/Makefile"
install -m 0644 "$stage/source/host/eth2-power-hold/m7_eth2_power_hold.c" "$module_build/m7_eth2_power_hold.c"
make -C "$kernel_src" O="$kernel_build" \
    ARCH=arm64 CROSS_COMPILE="$project/toolchain-14.3/bin/aarch64-none-linux-gnu-" \
    M="$module_build" modules < /dev/null
grep -aq 'vermagic=6.12.69-gf1b67c293213 SMP mod_unload aarch64' "$module_build/m7_eth2_power_hold.ko"
sha256sum "$module_build/m7_eth2_power_hold.ko"

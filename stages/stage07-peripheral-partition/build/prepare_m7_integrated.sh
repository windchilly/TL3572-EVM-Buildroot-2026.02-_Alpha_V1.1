#!/usr/bin/env bash
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly uni=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated}
readonly app_dir="$uni/demos/rk3572_mica/apps/openamp"
readonly overlay="$stage_root/source/overlay/uniproton/demos/rk3572_mica/apps/openamp"
# Fresh M6 + 0001/0002/0003; legacy 0004/0005/0006 hooks are not stacked.
M7_CAN_IRQ_TEST=ON UNIPROTON_ROOT="$uni" bash "$stage_root/build/prepare_m7_uniproton.sh"
git -C "$uni" apply --check "$stage_root/source/patches/uniproton/0007-rk3572-integrated-hooks.patch"
git -C "$uni" apply "$stage_root/source/patches/uniproton/0007-rk3572-integrated-hooks.patch"
for source in rk3572_can_fd_test.c rk3572_can_fd_codec.h rk3572_rs232_test.c rk3572_rs232_codec.h \
              rk3572_rs485_test.c rk3572_integrated.c rk3572_integrated.h rk3572_integrated_command.h; do
    install -m 0644 "$overlay/$source" "$app_dir/$source"
done
# Modify only these copied drivers: runtime parameters, independent exports, repeat-run cleanup.
git -C "$uni" apply --check "$stage_root/source/patches/uniproton/0008-rk3572-integrated-runtime.patch"
git -C "$uni" apply "$stage_root/source/patches/uniproton/0008-rk3572-integrated-runtime.patch"
git -C "$uni" apply --check "$stage_root/source/patches/uniproton/0009-rk3572-integrated-mmu-boot-guard.patch"
git -C "$uni" apply "$stage_root/source/patches/uniproton/0009-rk3572-integrated-mmu-boot-guard.patch"
echo "Prepared cumulative firmware source: $uni"

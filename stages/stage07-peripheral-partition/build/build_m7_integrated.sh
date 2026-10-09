#!/usr/bin/env bash
set -euo pipefail
readonly uni=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
readonly demo="$uni/demos/rk3572_mica"
if ! grep -q '^option(M7_INTEGRATED_FIRMWARE ' "$demo/CMakeLists.txt"; then
    echo "Run prepare_m7_integrated.sh in a fresh source tree first" >&2; exit 1
fi
build_one()
{
    local name=$1 cpu=$2 sgi=$3 image=$4 mmu=$5
    local build_dir="$demo/build/m7-integrated-$name"
    cmake -S "$demo" -B "$build_dir" \
        -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="$toolchain" \
        -DMCS_CLIENT_CPU_ID:STRING="$cpu" -DMCS_NOTIFY_SGI_ID:STRING="$sgi" \
        -DMCS_IMAGE_ADDR:STRING="$image" -DMCS_MMU_ADDR:STRING="$mmu" \
        -DM7_CAN_DIRECT_TEST:BOOL=OFF -DM7_CAN_IRQ_TEST:BOOL=OFF -DM7_INTEGRATED_FIRMWARE:BOOL=ON
    cmake --build "$build_dir" --target rk3572_mica --parallel
    cp "$build_dir/rk3572_mica" "$demo/build/tl3572-m7-integrated-$name.elf"
    sha256sum "$demo/build/tl3572-m7-integrated-$name.elf"
}
build_one up-a 4 8 0x7b200000 0x7ba00000
build_one up-b 5 9 0x7c200000 0x7ca00000

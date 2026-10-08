#!/usr/bin/env bash
set -euo pipefail

readonly uniproton_root=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7}
readonly toolchain_path=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
readonly demo_dir="${uniproton_root}/demos/rk3572_mica"

build_one()
{
    local name=$1 cpu=$2 sgi=$3 image=$4 mmu=$5
    local build_dir="${demo_dir}/build/m7-can-${name}"
    local output="${demo_dir}/build/tl3572-m7-can-${name}.elf"

    cmake -S "${demo_dir}" -B "${build_dir}" \
        -DAPP:STRING=rk3572_mica \
        -DTOOLCHAIN_PATH:STRING="${toolchain_path}" \
        -DCPU_TYPE:STRING=rk3572_mica \
        -DMCS_CLIENT_CPU_ID:STRING="${cpu}" \
        -DMCS_NOTIFY_SGI_ID:STRING="${sgi}" \
        -DMCS_IMAGE_ADDR:STRING="${image}" \
        -DMCS_MMU_ADDR:STRING="${mmu}" \
        -DM7_CAN_DIRECT_TEST:BOOL=ON
    cmake --build "${build_dir}" --target rk3572_mica --parallel
    cp "${build_dir}/rk3572_mica" "${output}"
    sha256sum "${output}"
}

build_one up-a 4 8 0x7b200000 0x7ba00000
build_one up-b 5 9 0x7c200000 0x7ca00000

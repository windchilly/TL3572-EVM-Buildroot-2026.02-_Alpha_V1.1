#!/usr/bin/env bash
set -euo pipefail
readonly uni=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-can-fd}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
readonly profile=${M7_CAN_FD_PROFILE:-0}
case "${profile}" in 0|2|4) ;; *) echo "M7_CAN_FD_PROFILE must be 0, 2 or 4" >&2; exit 1 ;; esac
readonly demo="${uni}/demos/rk3572_mica"
if ! grep -q '^option(M7_CAN_FD_TEST ' "${demo}/CMakeLists.txt"; then
    echo "Prepare a fresh source tree with prepare_m7_can_fd.sh first" >&2; exit 1
fi
build_one()
{
    local name=$1 cpu=$2 sgi=$3 image=$4 mmu=$5
    local build_dir="${demo}/build/m7-can-fd${profile}-${name}"
    local output="${demo}/build/tl3572-m7-can-fd${profile}-${name}.elf"
    cmake -S "${demo}" -B "${build_dir}" \
        -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="${toolchain}" \
        -DCPU_TYPE:STRING=rk3572_mica -DMCS_CLIENT_CPU_ID:STRING="${cpu}" \
        -DMCS_NOTIFY_SGI_ID:STRING="${sgi}" -DMCS_IMAGE_ADDR:STRING="${image}" \
        -DMCS_MMU_ADDR:STRING="${mmu}" -DM7_CAN_DIRECT_TEST:BOOL=ON \
        -DM7_CAN_IRQ_TEST:BOOL=ON -DM7_CAN_FD_TEST:BOOL=ON \
        -DM7_CAN_FD_PROFILE:STRING="${profile}"
    cmake --build "${build_dir}" --target rk3572_mica --parallel
    cp "${build_dir}/rk3572_mica" "${output}"
    sha256sum "${output}"
}
build_one up-a 4 8 0x7b200000 0x7ba00000
build_one up-b 5 9 0x7c200000 0x7ca00000

#!/usr/bin/env bash
set -euo pipefail
readonly uni=${UNIPROTON_ROOT:-/home/openeuler/build/tl3572-2oo3/src/UniProton-m7-rs232}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
readonly baud=${M7_RS232_BAUD:-115200}
case "${baud}" in 9600|38400|115200) ;; *) echo "Unsupported M7_RS232_BAUD" >&2; exit 1 ;; esac
readonly demo="${uni}/demos/rk3572_mica"
if ! grep -q '^option(M7_RS232_TEST ' "${demo}/CMakeLists.txt"; then
    echo "Run prepare_m7_rs232.sh in a fresh source tree first" >&2; exit 1
fi
build_one()
{
    local name=$1 cpu=$2 sgi=$3 image=$4 mmu=$5
    local build_dir="${demo}/build/m7-rs232-${baud}-${name}"
    cmake -S "${demo}" -B "${build_dir}" \
        -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="${toolchain}" \
        -DCPU_TYPE:STRING=rk3572_mica -DMCS_CLIENT_CPU_ID:STRING="${cpu}" \
        -DMCS_NOTIFY_SGI_ID:STRING="${sgi}" -DMCS_IMAGE_ADDR:STRING="${image}" \
        -DMCS_MMU_ADDR:STRING="${mmu}" -DM7_CAN_DIRECT_TEST:BOOL=OFF \
        -DM7_CAN_IRQ_TEST:BOOL=OFF -DM7_RS232_TEST:BOOL=ON -DM7_RS232_BAUD:STRING="${baud}"
    cmake --build "${build_dir}" --target rk3572_mica --parallel
    cp "${build_dir}/rk3572_mica" "${demo}/build/tl3572-m7-rs232-${baud}-${name}.elf"
    sha256sum "${demo}/build/tl3572-m7-rs232-${baud}-${name}.elf"
}
build_one up-a 4 8 0x7b200000 0x7ba00000
build_one up-b 5 9 0x7c200000 0x7ca00000

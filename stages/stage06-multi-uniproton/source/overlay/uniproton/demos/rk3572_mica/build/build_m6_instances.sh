#!/usr/bin/env bash
set -euo pipefail

export TOOLCHAIN_PATH=/home/openeuler/build/tl3572-2oo3/toolchain-14.3
export TOOLCHAIN_GCC_PATH=${TOOLCHAIN_PATH}/bin/aarch64-none-linux-gnu-gcc

readonly APP=rk3572_mica

sh ./build_static.sh "${APP}"
sh ./build_openamp.sh "${TOOLCHAIN_PATH}"

build_instance()
{
    local instance_name=$1
    local cpu_id=$2
    local sgi_id=$3
    local image_addr=$4
    local mmu_addr=$5
    local build_dir="m6-${instance_name}"
    local output="rk3572-uniproton-${instance_name}"

    cmake -S .. -B "${build_dir}" \
        -DAPP:STRING="${APP}" \
        -DTOOLCHAIN_PATH:STRING="${TOOLCHAIN_PATH}" \
        -DCPU_TYPE:STRING="rk3572_mica" \
        -DMCS_CLIENT_CPU_ID:STRING="${cpu_id}" \
        -DMCS_NOTIFY_SGI_ID:STRING="${sgi_id}" \
        -DMCS_IMAGE_ADDR:STRING="${image_addr}" \
        -DMCS_MMU_ADDR:STRING="${mmu_addr}"
    cmake --build "${build_dir}" --target "${APP}" --parallel

    cp "${build_dir}/${APP}" "${output}.elf"
    "${TOOLCHAIN_PATH}/bin/aarch64-none-elf-objcopy" \
        -O binary "${output}.elf" "${output}.bin"
    "${TOOLCHAIN_PATH}/bin/aarch64-none-elf-objdump" \
        -D "${output}.elf" > "${output}.asm"
}

# Keep the two client contracts explicit and reviewable in one place.
build_instance up-a 4 8 0x7b200000 0x7ba00000
build_instance up-b 5 9 0x7c200000 0x7ca00000

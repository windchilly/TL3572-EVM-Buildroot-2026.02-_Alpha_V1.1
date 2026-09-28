#!/usr/bin/env bash
set -euo pipefail

readonly project=/home/openeuler/build/tl3572-2oo3
readonly repo=${REPRO_REPO:-/repo}
readonly mode=${1:-m6}
readonly toolchain="${project}/toolchain-14.3"
export TOOLCHAIN_PATH="${toolchain}"
export TOOLCHAIN_GCC_PATH="${toolchain}/bin/aarch64-none-linux-gnu-gcc"

case "${mode}" in
    m6) readonly uni="${project}/src/UniProton" ;;
    m7)
        readonly uni="${project}/src/UniProton-m7"
        test ! -e "${uni}"
        mkdir "${uni}"
        tar -xzf "${repo}/repro-inputs/stage01-05/upstream/UniProton.tar.gz" -C "${uni}"
        tar -xzf "${repo}/repro-inputs/rk3572/uniproton-m6-complete-overlay.tar.gz" -C "${uni}"
        m7="${repo}/stages/stage07-peripheral-partition"
        git -C "${uni}" apply --check "${m7}/source/patches/uniproton/0001-dual-boot-log-and-uart0-isolation.patch"
        git -C "${uni}" apply "${m7}/source/patches/uniproton/0001-dual-boot-log-and-uart0-isolation.patch"
        install -m 0644 "${m7}/source/overlay/uniproton/demos/rk3572_mica/bsp/print.c" "${uni}/demos/rk3572_mica/bsp/print.c"
        ;;
    *) echo 'Usage: build_uniproton.sh m6|m7' >&2; exit 2 ;;
esac
readonly demo="${uni}/demos/rk3572_mica"
mkdir -p "${demo}/libs"
cp "${uni}/platform/libboundscheck/include/"* "${demo}/include/"
cd "${uni}"
python3 build.py rk3572
# The upstream Python entry point can exit zero after a build failure. Demand
# the actual archives before continuing, not just a successful process status.
test -s output/UniProton/lib/rk3572/libRK3572.a
test -s output/libboundscheck/lib/rk3572/libCortexMXsec_c.lib
cp output/UniProton/lib/rk3572/* "${demo}/libs/"
cp output/libboundscheck/lib/rk3572/* "${demo}/libs/"
cp -a output/libc "${demo}/include/"
cp -a src/include/uapi/. "${demo}/include/"
cp build/uniproton_config/config_armv8_rk3572/prt_buildef.h "${demo}/include/"
cd "${demo}/component"
test ! -e libmetal
test ! -e open-amp
tar -xzf libmetal-2022.10.0.tar.gz
mv libmetal-2022.10.0 libmetal
patch -p1 -d libmetal < UniProton-patch-for-libmetal.patch
tar -xzf openamp-2022.10.1.tar.gz
mv openamp-2022.10.1 open-amp
patch -p1 -d open-amp < UniProton-patch-for-openamp.patch
for dependency in libmetal open-amp; do
    cmake -S "${demo}/component/${dependency}" -B "${demo}/build/${dependency}/build" \
        -DCMAKE_TOOLCHAIN_FILE="${demo}/component/${dependency}/cmake/platforms/uniproton_arm64_gcc.cmake" \
        -DTOOLCHAIN_PATH:STRING="${toolchain}" -DWITH_DOC=OFF -DWITH_EXAMPLES=OFF \
        -DWITH_TESTS=OFF -DWITH_DEFAULT_LOGGER=OFF -DWITH_SHARED_LIB=OFF
    cmake --build "${demo}/build/${dependency}/build" --parallel "${REPRO_JOBS:-8}"
    DESTDIR="${demo}/build/${dependency}/output" cmake --install "${demo}/build/${dependency}/build"
    cp "${demo}/build/${dependency}/output/usr/local/lib/"*.a "${demo}/libs/"
done
if [[ "${mode}" = m7 ]]; then
    UNIPROTON_ROOT="${uni}" bash "${repo}/stages/stage07-peripheral-partition/build/build_m7_observability.sh"
else
    for name in up-a up-b; do
        if [[ "${name}" = up-a ]]; then
            cpu=4; sgi=8; image=0x7b200000; mmu=0x7ba00000
        else
            cpu=5; sgi=9; image=0x7c200000; mmu=0x7ca00000
        fi
        cmake -S "${demo}" -B "${demo}/build/m6-${name}" \
            -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="${toolchain}" \
            -DCPU_TYPE:STRING=rk3572_mica -DMCS_CLIENT_CPU_ID:STRING="${cpu}" \
            -DMCS_NOTIFY_SGI_ID:STRING="${sgi}" -DMCS_IMAGE_ADDR:STRING="${image}" \
            -DMCS_MMU_ADDR:STRING="${mmu}"
        cmake --build "${demo}/build/m6-${name}" --target rk3572_mica --parallel "${REPRO_JOBS:-8}"
        cp "${demo}/build/m6-${name}/rk3572_mica" "${demo}/build/tl3572-m6-${name}.elf"
        sha256sum "${demo}/build/tl3572-m6-${name}.elf"
    done
fi

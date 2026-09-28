#!/usr/bin/env bash
set -euo pipefail

# Build only the M7 daemon; do not alter the M6 source, image or dependency libraries.
readonly project_root=${PROJECT_ROOT:-/home/openeuler/build/tl3572-2oo3}
readonly mcs_root=${MCS_ROOT:-${project_root}/src/mcs-m7}
readonly toolchain_path=${TOOLCHAIN_PATH:-${project_root}/toolchain-14.3}
readonly components=${SYSROOT_COMPONENTS:-${project_root}/build/build-tl3572/tmp/sysroots-components/aarch64}
readonly build_dir=${MICAD_BUILD_DIR:-${project_root}/build-micad-m7}

for dependency in libmetal openamp; do
    test -d "${components}/${dependency}/usr/lib64"
done
test -d "${components}/sysfsutils/lib64"
test -f "${mcs_root}/mica/micad/services/rpc/rpc_backend.c"
grep -q 'rpc_service_users' "${mcs_root}/mica/micad/services/rpc/rpc_backend.c"

cmake -S "${mcs_root}" -B "${build_dir}" \
    -DCMAKE_SYSTEM_NAME=Linux \
    -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
    -DCMAKE_C_COMPILER="${toolchain_path}/bin/aarch64-none-linux-gnu-gcc" \
    -DCMAKE_CXX_COMPILER="${toolchain_path}/bin/aarch64-none-linux-gnu-g++" \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DCMAKE_C_FLAGS_RELWITHDEBINFO="-O2 -g -DNDEBUG -D_GNU_SOURCE= -fPIE" \
    -DCMAKE_SKIP_RPATH=TRUE \
    -DCMAKE_C_STANDARD_INCLUDE_DIRECTORIES="${components}/libmetal/usr/include;${components}/openamp/usr/include;${components}/sysfsutils/usr/include" \
    -DCMAKE_EXE_LINKER_FLAGS="-pthread -pie -Wl,-z,relro,-z,now,--hash-style=gnu -L${components}/libmetal/usr/lib64 -L${components}/openamp/usr/lib64 -Wl,-rpath-link,${components}/sysfsutils/lib64"
cmake --build "${build_dir}" --target micad --parallel
sha256sum "${build_dir}/mica/micad/micad"
"${toolchain_path}/bin/aarch64-none-linux-gnu-readelf" -h -l -d "${build_dir}/mica/micad/micad"

#!/usr/bin/env bash
set -euo pipefail

readonly repo=${REPRO_REPO:-/repo}
readonly project=/home/openeuler/build/tl3572-2oo3
readonly inputs="${repo}/repro-inputs/rk3572"

test "$(id -u)" = 1000
test ! -e "${project}"
test ! -e /home/openeuler/build/downloads
cd "${inputs}"
sha256sum -c SHA256SUMS
cd "${repo}/repro-inputs/stage01-05"
sha256sum -c SHA256SUMS
mkdir -p "${project}/src" "${project}/build/build-tl3572/conf" "${project}/logs"
for baseline in "${repo}"/repro-inputs/stage01-05/upstream/*.tar.gz; do
    name=$(basename "${baseline}" .tar.gz)
    mkdir "${project}/src/${name}"
    tar -xzf "${baseline}" -C "${project}/src/${name}"
done
tar -xzf "${inputs}/openeuler-packages.tar.gz" -C "${project}"
tar -xzf "${inputs}/downloads.tar.gz" -C /home/openeuler/build
# This overlay contains the effective M6 source, including previously missing
# libboundscheck. No library or compiler output is taken from the old host.
tar -xzf "${inputs}/uniproton-m6-complete-overlay.tar.gz" -C "${project}/src/UniProton"
cp -a "${repo}/repro-inputs/meta-tl3572-stage3" "${project}/"
cp -a "${repo}/repro-inputs/build-conf/." "${project}/build/build-tl3572/conf/"
cp -a "${repo}/repro-inputs/.oebuild" "${project}/"
mkdir "${project}/toolchain-14.3"
toolchain_archive="${repo}/4-软件资料/Linux/Tools/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu.tar.gz"
printf '%s  %s\n' 'c7609e94851a47a5f475fb91eee091c8ca9eef13f31bad2e43d12d11bb1f7861' "${toolchain_archive}" | sha256sum -c -
tar -xzf "${toolchain_archive}" --strip-components=1 -C "${project}/toolchain-14.3"
for tool in gcc g++ ar ld nm objcopy objdump readelf strip ranlib; do
    test -x "${project}/toolchain-14.3/bin/aarch64-none-linux-gnu-${tool}"
    ln -s "aarch64-none-linux-gnu-${tool}" "${project}/toolchain-14.3/bin/aarch64-none-elf-${tool}"
done
# The original workspace uses an empty specs compatibility file, not newlib's
# libnosys. The application links with -nostdlib against its own RTOS libraries.
install -m 0644 "${inputs}/config/nosys.specs" "${project}/toolchain-14.3/lib/gcc/aarch64-none-linux-gnu/14.3.1/nosys.specs"
# Keep the upstream URI mapping but disable git checkout/network updates of
# archived packaging trees. Fix the epoch because these archives omit .git.
printf '\n# Frozen-source reproduction; no reuse of the old build/sstate.\nOPENEULER_FETCH = "disable"\nBB_NO_NETWORK = "1"\nSOURCE_DATE_EPOCH = "1787652448"\nBB_NUMBER_THREADS = "%s"\nPARALLEL_MAKE = "-j %s"\n' \
    "${REPRO_JOBS:-8}" "${REPRO_JOBS:-8}" >> "${project}/build/build-tl3572/conf/local.conf"
"${project}/toolchain-14.3/bin/aarch64-none-linux-gnu-gcc" --version | head -1
echo '0b2f6c2c7842e7839a233a8abda4f0ac4b92dcaa0580d6bacd90771c482a218a  /usr1/openeuler/gcc/openeuler_gcc_arm64le/bin/aarch64-openeuler-linux-gnu-gcc' | sha256sum -c -
printf 'Prepared fresh project: %s\n' "${project}"

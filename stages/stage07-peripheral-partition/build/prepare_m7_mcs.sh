#!/usr/bin/env bash
set -euo pipefail

readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly repo_root=$(cd "${stage_root}/../.." && pwd)
readonly project_root=${PROJECT_ROOT:-/home/openeuler/build/tl3572-2oo3}
readonly baseline=${MCS_BASELINE_ROOT:-${project_root}/src/mcs}
readonly destination=${MCS_ROOT:-${project_root}/src/mcs-m7}
readonly m6_patches="${repo_root}/repro-inputs/meta-tl3572-stage3/recipes-mcs/mcs-linux/files"

# Baseline is the pinned, unpatched upstream MCS snapshot, not a Yocto work directory.
test -f "${baseline}/mica/micad/services/rpc/rpc_backend.c"
if [[ -e "${destination}" ]]; then
    echo "Destination already exists; refusing to overwrite: ${destination}" >&2
    exit 1
fi
cp -a "${baseline}" "${destination}"
for patch_file in \
    "${m6_patches}/0001-mcs-rpmsg-tty-full-payload.patch" \
    "${m6_patches}/0002-baremetal-rproc-route-dual-sgi-events.patch" \
    "${stage_root}/source/patches/mcs/0003-rpc-shared-log-lifecycle.patch"; do
    git -C "${destination}" apply --check "${patch_file}"
    git -C "${destination}" apply "${patch_file}"
done
echo "Prepared M7 MCS source: ${destination}"

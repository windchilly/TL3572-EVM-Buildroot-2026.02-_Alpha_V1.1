#!/usr/bin/env bash
set -euo pipefail

readonly project=/home/openeuler/build/tl3572-2oo3
readonly repo=${REPRO_REPO:-/repo}
readonly mode=${1:-m6-image}
cd "${project}"
set +u
source /opt/buildtools/nativesdk/environment-setup-x86_64-openeulersdk-linux
source src/yocto-poky/oe-init-build-env "${project}/build/build-tl3572" >/dev/null
set -u
case "${mode}" in
    fetch) bitbake tl3572-openeuler-mcs-image --runall=fetch ;;
    m6-image) bitbake tl3572-openeuler-mcs-image ;;
    m7-mcs)
        bitbake -r "${repo}/repro-inputs/rk3572/config/m7.conf" mcs-linux
        ;;
    *) echo 'Usage: build_yocto.sh fetch|m6-image|m7-mcs' >&2; exit 2 ;;
esac

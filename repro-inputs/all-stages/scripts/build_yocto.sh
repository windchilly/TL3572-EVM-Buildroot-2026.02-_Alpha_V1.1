#!/usr/bin/env bash
set -euo pipefail
readonly project=/home/openeuler/build/tl3572-2oo3
readonly stage=${1:?stage}
readonly mode=${2:?fetch or image}
if [[ "${stage}" = stage02 ]]; then
    build="${project}/build/build-rootfs"
    target=openeuler-image
else
    build="${project}/build/build-tl3572"
    target=tl3572-openeuler-mcs-image
fi
set +u
source /opt/buildtools/nativesdk/environment-setup-x86_64-openeulersdk-linux
source "${project}/src/yocto-poky/oe-init-build-env" "${build}" >/dev/null
set -u
case "${mode}" in
    fetch) bitbake "${target}" --runall=fetch ;;
    image) bitbake "${target}" ;;
    *) exit 2 ;;
esac

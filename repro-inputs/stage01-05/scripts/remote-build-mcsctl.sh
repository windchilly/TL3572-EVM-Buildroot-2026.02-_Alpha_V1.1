#!/bin/bash
set -o pipefail

status_file=/home/openeuler/build/tl3572-2oo3/logs/stage2-mcsctl.status
log_file=/home/openeuler/build/tl3572-2oo3/logs/stage2-bitbake-openeuler-image-mcsctl.log

rm -f "${status_file}"
source /home/openeuler/build/tl3572-2oo3/src/yocto-poky/oe-init-build-env \
    /home/openeuler/build/tl3572-2oo3/build/build-rootfs >/dev/null
bitbake openeuler-image >"${log_file}" 2>&1
result=$?
printf '%s\n' "${result}" >"${status_file}"
exit "${result}"

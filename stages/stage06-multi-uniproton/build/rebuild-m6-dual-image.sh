#!/usr/bin/env bash
set -eo pipefail

source /home/openeuler/build/tl3572-2oo3/src/yocto-poky/oe-init-build-env \
    /home/openeuler/build/tl3572-2oo3/build/build-tl3572

bitbake linux-tl3572 -c clean
bitbake mcs-linux -c clean
bitbake tl3572-openeuler-mcs-image

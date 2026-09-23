#!/bin/bash
set -o pipefail

base=/home/openeuler/build/tl3572-2oo3
build=${base}/build/build-tl3572
log=${base}/logs/stage3-bitbake-tl3572-image.log
status=${base}/logs/stage3-bitbake-tl3572-image.status
. /opt/buildtools/nativesdk/environment-setup-x86_64-openeulersdk-linux
hosttools_extra=${base}/hosttools-extra
mkdir -p ${hosttools_extra}
ln -snf /opt/buildtools/nativesdk/sysroots/x86_64-openeulersdk-linux/usr/bin/compile_et \
    ${hosttools_extra}/compile_et
ln -snf /opt/buildtools/nativesdk/sysroots/x86_64-openeulersdk-linux/usr/bin/tar \
    ${hosttools_extra}/tar
export PATH=${hosttools_extra}:${PATH}

rm -f ${status}
source ${base}/src/yocto-poky/oe-init-build-env ${build} >/dev/null
bitbake tl3572-openeuler-mcs-image >${log} 2>&1
result=$?
printf '%s\n' ${result} >${status}
exit ${result}

#!/bin/bash
set -eo pipefail

base=/home/openeuler/build/tl3572-2oo3
stage2_build=${base}/build/build-rootfs
stage3_build=${base}/build/build-tl3572
stage3_layer=${base}/meta-tl3572-stage3
. /opt/buildtools/nativesdk/environment-setup-x86_64-openeulersdk-linux
hosttools_extra=${base}/hosttools-extra
mkdir -p ${hosttools_extra}
ln -snf /opt/buildtools/nativesdk/sysroots/x86_64-openeulersdk-linux/usr/bin/compile_et \
    ${hosttools_extra}/compile_et
ln -snf /opt/buildtools/nativesdk/sysroots/x86_64-openeulersdk-linux/usr/bin/tar \
    ${hosttools_extra}/tar
export PATH=${hosttools_extra}:${PATH}

mkdir -p ${stage3_build}
if [ ! -f ${stage3_build}/conf/local.conf ]; then
    cp -a ${stage2_build}/conf ${stage3_build}/
fi

cp -f ${base}/local-stage3.conf ${stage3_build}/conf/tl3572-stage3.conf

sed -i \
    -e 's|MACHINE ??= "qemu-aarch64"|MACHINE ??= "tl3572-evm"|' \
    -e 's|MACHINE = "qemu-aarch64"|MACHINE = "tl3572-evm"|' \
    -e 's|/home/openeuler/build/tl3572-2oo3/build/build-rootfs/tmp|/home/openeuler/build/tl3572-2oo3/build/build-tl3572/tmp|' \
    ${stage3_build}/conf/local.conf

# Remove only the old user-added stage-2 image block from the copied config.
sed -i '/# Stage 2 builds an AArch64 userspace seed/,$d' \
    ${stage3_build}/conf/local.conf

if ! grep -q '^require conf/tl3572-stage3.conf$' ${stage3_build}/conf/local.conf; then
    sed -i '$a require conf/tl3572-stage3.conf' ${stage3_build}/conf/local.conf
fi

sed -i \
    's|/home/openeuler/build/tl3572-2oo3/meta-tl3572 |/home/openeuler/build/tl3572-2oo3/meta-tl3572-stage3 |' \
    ${stage3_build}/conf/bblayers.conf

source ${base}/src/yocto-poky/oe-init-build-env ${stage3_build} >/dev/null

bitbake-layers show-layers
bitbake-layers show-recipes tl3572-openeuler-mcs-image
bitbake -e tl3572-openeuler-mcs-image | \
    grep -E '^(MACHINE|DEFAULTTUNE|TUNE_FEATURES|IMAGE_FSTYPES|IMAGE_ROOTFS_SIZE|KERNEL_DEVICETREE|ROOTFS_PACKAGE_ARCH)='

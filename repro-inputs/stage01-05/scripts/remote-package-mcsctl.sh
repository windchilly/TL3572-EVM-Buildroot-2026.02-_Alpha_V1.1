#!/bin/bash
set -euo pipefail

base=/home/openeuler/build/tl3572-2oo3
build=${base}/build/build-rootfs
deploy=${build}/tmp/deploy/images/qemu-aarch64
artifact=${base}/images/stage2-fix-mcsctl
image=$(readlink -f ${deploy}/openeuler-image-qemu-aarch64.ext4)
manifest=$(readlink -f ${deploy}/openeuler-image-qemu-aarch64.manifest)

mkdir -p ${artifact}
ln -f ${image} ${artifact}/rootfs-openeuler-tl3572-mcsctl.ext4
gzip -c ${image} >${artifact}/rootfs-openeuler-tl3572-mcsctl.ext4.gz.tmp
mv -f ${artifact}/rootfs-openeuler-tl3572-mcsctl.ext4.gz.tmp \
    ${artifact}/rootfs-openeuler-tl3572-mcsctl.ext4.gz
cp -f ${manifest} ${artifact}/rootfs.manifest
cp -f ${build}/compile.yaml ${artifact}/compile.yaml
cp -f ${base}/logs/stage2-bitbake-openeuler-image-mcsctl.log ${artifact}/build.log
cp -f ${base}/meta-tl3572/recipes-mcs/mcs-linux/mcsctl.bbappend ${artifact}/mcsctl.bbappend
e2fsck -fn ${image} >${artifact}/e2fsck.txt 2>&1

cd ${artifact}
sha256sum \
    rootfs-openeuler-tl3572-mcsctl.ext4 \
    rootfs-openeuler-tl3572-mcsctl.ext4.gz \
    rootfs.manifest \
    compile.yaml \
    build.log \
    mcsctl.bbappend \
    e2fsck.txt >SHA256SUMS

echo ARTIFACT=${artifact}
ls -lh ${artifact}
cat ${artifact}/SHA256SUMS

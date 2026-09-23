#!/bin/bash
set -e

base=/home/openeuler/build/tl3572-2oo3
build=${base}/build/build-rootfs
rootfs=${build}/tmp/work/qemu_aarch64-openeuler-linux/openeuler-image/1.0-r0/rootfs

echo BBAPPEND
ls -l ${base}/meta-tl3572/recipes-mcs/mcs-linux/mcsctl.bbappend

echo ROOTFS
ls -l ${rootfs}/usr/bin/mica ${rootfs}/usr/bin/mcsctl
printf 'mcsctl_target='
readlink ${rootfs}/usr/bin/mcsctl

echo RPM
rpmfile=$(find ${build}/tmp/deploy/rpm -type f -name 'mcsctl-1.0-r0.aarch64.rpm' -print -quit)
echo ${rpmfile}
rpm -qpl ${rpmfile} | grep '/usr/bin/'

echo DEPLOY
image=$(readlink -f ${build}/tmp/deploy/images/qemu-aarch64/openeuler-image-qemu-aarch64.ext4)
ls -lh ${image}

echo E2FSCK
e2fsck -fn ${image}
echo IMAGE=${image}

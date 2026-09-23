#!/bin/bash
set -euo pipefail

base=/home/openeuler/build/tl3572-2oo3
build=${base}/build/build-tl3572
deploy=${build}/tmp/deploy/images/tl3572-evm
rootfs=${build}/tmp/work/tl3572_evm-openeuler-linux/tl3572-openeuler-mcs-image/1.0-r0/rootfs

echo MACHINE_ARTIFACTS
ls -lh ${deploy}/tl3572-openeuler-mcs-image-tl3572-evm*.rootfs.ext4

echo BSP_IDENTITY
test -f ${rootfs}/usr/share/tl3572/vendor-overlay-info
ls -l ${rootfs}/usr/share/tl3572/vendor-overlay-info
ls -l ${rootfs}/usr/bin/mcsctl
readlink ${rootfs}/usr/bin/mcsctl

echo DIAGNOSTIC_TOOLS
for tool in findmnt ss getent; do
    test -x ${rootfs}/usr/bin/${tool} || test -x ${rootfs}/sbin/${tool}
    find ${rootfs}/usr/bin ${rootfs}/sbin -maxdepth 1 -name ${tool} -ls
done

echo NETWORK_POLICY
test ! -e ${rootfs}/etc/systemd/network/10-eth-static.network
cat ${rootfs}/etc/systemd/network/20-wired.network
cat ${rootfs}/etc/systemd/system/systemd-networkd-wait-online.service.d/20-tl3572-any-link.conf
test ! -e ${rootfs}/etc/systemd/system/multi-user.target.wants/dhcpcd.service

echo SERVICE_STATUS
test ! -e ${rootfs}/lib/systemd/system/auditd.service
echo auditd.service=absent
if [ -e ${rootfs}/lib/systemd/system/proc-fs-nfsd.mount ]; then
    echo proc-fs-nfsd.mount=present-known-issue
else
    echo proc-fs-nfsd.mount=absent
fi

echo VENDOR_ASSETS
test ! -d ${rootfs}/lib/modules/5.10.0-openeuler
test "$(find ${rootfs}/lib/modules -maxdepth 1 -type f -name '*.ko' | wc -l)" -ge 1
test "$(find ${rootfs}/lib/firmware -type f | wc -l)" -ge 1
find ${rootfs}/lib/modules -maxdepth 1 -type f -name '*.ko' | wc -l
find ${rootfs}/lib/firmware -type f | wc -l

echo PACKAGE_MANIFEST
manifest=$(readlink -f ${deploy}/tl3572-openeuler-mcs-image-tl3572-evm.manifest)
grep -E '^(tl3572-vendor-assets|util-linux-findmnt|iproute2-ss|mcsctl) ' ${manifest}
grep -E '^(audit|auditd|nfs-utils|nfs-utils-client|nfs-utils-mount) ' ${manifest} || true

echo E2FSCK
image=$(readlink -f ${deploy}/tl3572-openeuler-mcs-image-tl3572-evm.ext4)
e2fsck -fn ${image}

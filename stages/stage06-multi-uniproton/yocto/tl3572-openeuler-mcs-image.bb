SUMMARY = "openEuler Embedded root filesystem for TL3572-EVM MICA bring-up"
DESCRIPTION = "Board-scoped openEuler systemd image for the TL3572 BSP and later MICA integration"

require recipes-core/images/openeuler-image.bb

COMPATIBLE_MACHINE = "^tl3572-evm$"

# Milestone 1 reuses vendor 6.12.69 modules with the already validated
# boot.img.  There is deliberately no Yocto kernel ABI metadata until the
# linux-tl3572 provider lands in the next BSP milestone.
USE_DEPMOD = "0"

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
TL3572_UNIPROTON_UP_A_SHA256 = "9c5e55a268d9f59e180998848b79297945f2b7eb92ba6512d3869e9cd9ae89b8"
TL3572_UNIPROTON_UP_B_SHA256 = "3357eb979263332a7a4ee606e90fbec90ac0363977a908c5c3a6862c250edde4"
SRC_URI += " \
    file://20-wired.network \
    file://fstab \
    file://hostname \
"

# The board keeps the validated vendor boot.img during the first BSP milestone,
# so no generic kernel or qemu MCS kernel module belongs in this rootfs.
NO_RECOMMENDATIONS = "1"
IMAGE_INSTALL:remove = "packagegroup-kernel-modules packagegroup-mcs"
IMAGE_INSTALL:append = " \
    ethtool \
    dosfstools \
    mcs-linux \
    mcsctl \
    linux-tl3572 \
    screen \
    tl3572-vendor-assets \
    util-linux-findmnt \
    iproute2-ss \
    glibc-external-utils \
"
IMAGE_FEATURES:append = " debug-tweaks "

tl3572_bsp_rootfs_config () {
    install -d ${IMAGE_ROOTFS}/etc/systemd/network
    rm -f ${IMAGE_ROOTFS}/etc/systemd/network/10-eth-static.network
    # Image recipes do not necessarily run do_unpack before do_rootfs.  Read
    # these immutable board policy files directly from this layer.
    install -m 0644 ${THISDIR}/files/20-wired.network \
        ${IMAGE_ROOTFS}/etc/systemd/network/20-wired.network
    install -m 0644 ${THISDIR}/files/fstab ${IMAGE_ROOTFS}/etc/fstab
    install -m 0644 ${THISDIR}/files/hostname ${IMAGE_ROOTFS}/etc/hostname

    install -d ${IMAGE_ROOTFS}/oem ${IMAGE_ROOTFS}/userdata
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/getty.target.wants
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/network-online.target.wants
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/systemd-networkd-wait-online.service.d
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/micad.service.d
    install -d ${IMAGE_ROOTFS}/etc/mica
    install -d ${IMAGE_ROOTFS}/lib/firmware

    # Board-specific MCS runtime.  Keep only the two explicit TL3572 clients;
    # manual boot is intentional until start-order and isolation tests pass.
    rm -f ${IMAGE_ROOTFS}/etc/mica/*.conf
    rm -f ${IMAGE_ROOTFS}/lib/firmware/rk3572-uniproton*.elf
    install -m 0644 ${THISDIR}/files/tl3572-up-a.conf \
        ${IMAGE_ROOTFS}/etc/mica/tl3572-up-a.conf
    install -m 0644 ${THISDIR}/files/tl3572-up-b.conf \
        ${IMAGE_ROOTFS}/etc/mica/tl3572-up-b.conf
    install -m 0644 ${THISDIR}/files/rk3572-uniproton-up-a.elf \
        ${IMAGE_ROOTFS}/lib/firmware/rk3572-uniproton-up-a.elf
    install -m 0644 ${THISDIR}/files/rk3572-uniproton-up-b.elf \
        ${IMAGE_ROOTFS}/lib/firmware/rk3572-uniproton-up-b.elf

    up_a_sha256=$(sha256sum \
        ${IMAGE_ROOTFS}/lib/firmware/rk3572-uniproton-up-a.elf | awk '{print $1}')
    if [ "$up_a_sha256" != "${TL3572_UNIPROTON_UP_A_SHA256}" ]; then
        bbfatal "TL3572 UP-A firmware checksum mismatch: $up_a_sha256"
    fi
    up_b_sha256=$(sha256sum \
        ${IMAGE_ROOTFS}/lib/firmware/rk3572-uniproton-up-b.elf | awk '{print $1}')
    if [ "$up_b_sha256" != "${TL3572_UNIPROTON_UP_B_SHA256}" ]; then
        bbfatal "TL3572 UP-B firmware checksum mismatch: $up_b_sha256"
    fi

    install -m 0644 ${THISDIR}/files/mcs-km-load.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/mcs-km-load.service
    install -m 0644 ${THISDIR}/files/micad-mcs-km.conf \
        ${IMAGE_ROOTFS}/etc/systemd/system/micad.service.d/10-mcs-km.conf

    ln -snf /lib/systemd/system/serial-getty@.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/getty.target.wants/serial-getty@ttyFIQ0.service
    ln -snf /lib/systemd/system/systemd-networkd.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/systemd-networkd.service
    ln -snf /lib/systemd/system/systemd-resolved.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/systemd-resolved.service
    ln -snf /lib/systemd/system/systemd-networkd-wait-online.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/network-online.target.wants/systemd-networkd-wait-online.service

    printf '%s\n' \
        '[Service]' \
        'ExecStart=' \
        'ExecStart=/lib/systemd/systemd-networkd-wait-online --any --timeout=30' \
        > ${IMAGE_ROOTFS}/etc/systemd/system/systemd-networkd-wait-online.service.d/20-tl3572-any-link.conf

    rm -f ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/dhcpcd.service
    rm -f ${IMAGE_ROOTFS}/etc/systemd/system/network-online.target.wants/dhcpcd.service
    ln -snf /etc/systemd/system/mcs-km-load.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/mcs-km-load.service
    ln -snf /lib/systemd/system/micad.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/micad.service

    # The vendor 6.12 kernel provides no nfsd filesystem, so the static
    # proc-fs-nfsd.mount unit shipped with nfs-utils was the only failing
    # unit on M1 boards.  The packagegroup bbappends in this layer drop
    # nfs-utils entirely; this mask is defense in depth against any
    # future dependency path pulling it back in.
    ln -snf /dev/null ${IMAGE_ROOTFS}/etc/systemd/system/proc-fs-nfsd.mount

    # Stage-3 laboratory access.  Replace this with a key/password policy
    # before release hardening.
    if [ -f ${IMAGE_ROOTFS}/etc/ssh/sshd_config ]; then
        sed -i \
            -e 's/^[#[:space:]]*PermitRootLogin[[:space:]].*/PermitRootLogin yes/' \
            -e 's/^[#[:space:]]*PasswordAuthentication[[:space:]].*/PasswordAuthentication yes/' \
            -e 's/^[#[:space:]]*PermitEmptyPasswords[[:space:]].*/PermitEmptyPasswords yes/' \
            ${IMAGE_ROOTFS}/etc/ssh/sshd_config
    fi

    if [ -d ${IMAGE_ROOTFS}/etc/selinux ]; then
        printf '%s\n' 'SELINUX=disabled' 'SELINUXTYPE=targeted' \
            > ${IMAGE_ROOTFS}/etc/selinux/config
    fi

    if [ -e ${IMAGE_ROOTFS}/usr/share/zoneinfo/Asia/Shanghai ]; then
        ln -snf /usr/share/zoneinfo/Asia/Shanghai ${IMAGE_ROOTFS}/etc/localtime
    fi
}

ROOTFS_POSTPROCESS_COMMAND:append = " tl3572_bsp_rootfs_config;"

tl3572_bsp_image_sanitize () {
    # Never ship the generic openEuler 5.10 module directory with the vendor
    # TL3572 6.12.69 boot image.
    if [ -d ${IMAGE_ROOTFS}/lib/modules/5.10.0-openeuler ]; then
        rm -rf ${IMAGE_ROOTFS}/lib/modules/5.10.0-openeuler
    fi

    find ${IMAGE_ROOTFS}/lib/modules -maxdepth 1 -type f -name '*.ko' \
        -exec chmod 0644 {} +
    find ${IMAGE_ROOTFS}/lib/firmware -type d -exec chmod 0755 {} +
    find ${IMAGE_ROOTFS}/lib/firmware -type f -exec chmod 0644 {} +
}

IMAGE_PREPROCESS_COMMAND:append = " tl3572_bsp_image_sanitize;"

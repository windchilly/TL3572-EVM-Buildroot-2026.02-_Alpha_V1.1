FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
TL3572_STAGE2_FILES := "${THISDIR}/files"

# qemu-aarch64 package groups recommend their 5.10 kernel modules through
# IPv6/NFS/iptables.  The TL3572 keeps the vendor 6.12 boot.img, so only
# explicitly selected userspace packages belong in this rootfs.
NO_RECOMMENDATIONS = "1"

SRC_URI += " \
    file://20-wired.network \
    file://fstab \
    file://hostname \
"

tl3572_stage2_config () {
    install -d ${IMAGE_ROOTFS}/etc/systemd/network
    # Defense in depth for already-populated sstate/rootfs trees.  The
    # os-base bbappend removes this at package creation time as well.
    rm -f ${IMAGE_ROOTFS}/etc/systemd/network/10-eth-static.network
    install -m 0644 ${TL3572_STAGE2_FILES}/20-wired.network \
        ${IMAGE_ROOTFS}/etc/systemd/network/20-wired.network
    install -m 0644 ${TL3572_STAGE2_FILES}/fstab ${IMAGE_ROOTFS}/etc/fstab
    install -m 0644 ${TL3572_STAGE2_FILES}/hostname ${IMAGE_ROOTFS}/etc/hostname

    # Board-matched modules and firmware captured from the known-good vendor
    # Buildroot image.  The vendor uses a flat /lib/modules layout and loads
    # optional Wi-Fi/BT modules with insmod, so keep that layout unchanged.
    tar -xzf ${TL3572_STAGE2_FILES}/tl3572-vendor-overlay.tar.gz \
        -C ${IMAGE_ROOTFS}

    install -d ${IMAGE_ROOTFS}/oem ${IMAGE_ROOTFS}/userdata
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/getty.target.wants
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/network-online.target.wants
    install -d ${IMAGE_ROOTFS}/etc/systemd/system/systemd-networkd-wait-online.service.d

    ln -snf /lib/systemd/system/serial-getty@.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/getty.target.wants/serial-getty@ttyFIQ0.service
    ln -snf /lib/systemd/system/systemd-networkd.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/systemd-networkd.service
    ln -snf /lib/systemd/system/systemd-resolved.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/systemd-resolved.service
    ln -snf /lib/systemd/system/systemd-networkd-wait-online.service \
        ${IMAGE_ROOTFS}/etc/systemd/system/network-online.target.wants/systemd-networkd-wait-online.service

    # TL3572 has two Ethernet MACs and either port may be intentionally
    # unplugged.  Consider network-online reached when any managed link is
    # online instead of failing while waiting for both ports.
    printf '%s\n' \
        '[Service]' \
        'ExecStart=' \
        'ExecStart=/lib/systemd/systemd-networkd-wait-online --any --timeout=30' \
        > ${IMAGE_ROOTFS}/etc/systemd/system/systemd-networkd-wait-online.service.d/20-tl3572-any-link.conf

    # systemd-networkd is authoritative.  Remove legacy dhcpcd enablement
    # created by package post-install scripts without deleting the package.
    rm -f ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/dhcpcd.service
    rm -f ${IMAGE_ROOTFS}/etc/systemd/system/network-online.target.wants/dhcpcd.service

    # Stage-2 lab access only: the debug-tweaks root account has no password.
    # Keep serial and SSH recovery paths available while validating the new
    # userspace.  This must be replaced by keys/password policy before release.
    if [ -f ${IMAGE_ROOTFS}/etc/ssh/sshd_config ]; then
        sed -i \
            -e 's/^[#[:space:]]*PermitRootLogin[[:space:]].*/PermitRootLogin yes/' \
            -e 's/^[#[:space:]]*PasswordAuthentication[[:space:]].*/PasswordAuthentication yes/' \
            -e 's/^[#[:space:]]*PermitEmptyPasswords[[:space:]].*/PermitEmptyPasswords yes/' \
            ${IMAGE_ROOTFS}/etc/ssh/sshd_config
    fi

    # MICA userspace is staged now; no RTOS is allowed to auto-start in stage 2.
    rm -f ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/micad.service

    if [ -d ${IMAGE_ROOTFS}/etc/selinux ]; then
        printf '%s\n' 'SELINUX=disabled' 'SELINUXTYPE=targeted' \
            > ${IMAGE_ROOTFS}/etc/selinux/config
    fi

    if [ -e ${IMAGE_ROOTFS}/usr/share/zoneinfo/Asia/Shanghai ]; then
        ln -snf /usr/share/zoneinfo/Asia/Shanghai ${IMAGE_ROOTFS}/etc/localtime
    fi
}

ROOTFS_POSTPROCESS_COMMAND:append = " tl3572_stage2_config;"

tl3572_stage2_image_sanitize () {
    # systemd-depmod can create this empty QEMU-kernel index after rootfs
    # post-processing.  Remove only the exact known-incompatible directory at
    # the final image-preparation boundary.
    if [ -d ${IMAGE_ROOTFS}/lib/modules/5.10.0-openeuler ]; then
        rm -rf ${IMAGE_ROOTFS}/lib/modules/5.10.0-openeuler
    fi

    find ${IMAGE_ROOTFS}/lib/modules -maxdepth 1 -type f -name '*.ko' \
        -exec chmod 0644 {} +
    find ${IMAGE_ROOTFS}/lib/firmware -type d -exec chmod 0755 {} +
    find ${IMAGE_ROOTFS}/lib/firmware -type f -exec chmod 0644 {} +
}

IMAGE_PREPROCESS_COMMAND:append = " tl3572_stage2_image_sanitize;"

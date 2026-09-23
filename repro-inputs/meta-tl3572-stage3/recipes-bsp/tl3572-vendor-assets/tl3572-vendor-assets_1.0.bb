SUMMARY = "TL3572 vendor-matched kernel modules and firmware"
DESCRIPTION = "Modules and firmware captured from the validated TL3572 Buildroot image for Linux 6.12.69"
LICENSE = "CLOSED"

COMPATIBLE_MACHINE = "^tl3572-evm$"
PACKAGE_ARCH = "${MACHINE_ARCH}"

# Keep the archive intact.  do_install extracts it directly into ${D}; letting
# the generic unpack task expand it would remove the archive before install.
SRC_URI = "file://tl3572-vendor-overlay.tar.gz;unpack=0"
S = "${WORKDIR}"

do_compile[noexec] = "1"

do_install() {
    install -d ${D}
    tar -xzf ${WORKDIR}/tl3572-vendor-overlay.tar.gz -C ${D}

    # The source archive was produced on Windows and records 0777 for every
    # entry.  Normalize it before RPM packaging so shared directories such as
    # /lib and /lib/firmware match the system packages that also own them.
    find ${D} -type d -exec chmod 0755 {} +
    find ${D} -type f -exec chmod 0644 {} +
}

FILES:${PN} += " \
    /lib/modules \
    /lib/firmware \
    ${datadir}/tl3572 \
"

INHIBIT_PACKAGE_STRIP = "1"
INSANE_SKIP:${PN} += "already-stripped"

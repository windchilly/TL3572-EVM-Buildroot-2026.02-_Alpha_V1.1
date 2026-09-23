SUMMARY = "TL3572 vendor Linux 6.12.69 with openEuler MICA/MCS enablement (stage 6)"
DESCRIPTION = "Rebuilds the board-validated stage-6 kernel with the Arm GNU 14.3 \
vendor toolchain (dual reserved-SGI exports for mcs_km and persistent MCS CPU reservation), \
assembles the Rockchip external-data FIT boot.img from the vendor DTB plus the MCS \
overlay, and ships the mcs_km.ko management module for the 6.12.69-gf1b67c293213 ABI."
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=6bc538ed5bd9a7fc9398086aedcd7e46"

inherit deploy

COMPATIBLE_MACHINE = "^tl3572-evm$"
PACKAGE_ARCH = "${MACHINE_ARCH}"

# This recipe is deliberately NOT the virtual/kernel provider.  The stage-3
# rootfs flow (linux-dummy plus vendor module files) stays untouched; this
# recipe supplies the boot.img artifacts and the mcs_km.ko module matching
# the vendor 6.12.69-gf1b67c293213 ABI.
#
# Pinned inputs and their provenance:
#   linux-6.12.69-v1.0-gf1b67c2.tar.gz : repacked (topdir added, dead .git
#       dropped) from the vendor tarball, SHA256
#       186face3889200078ef67a8d97f1ed587e4e1d1e30683a81566d5e85a2d60608
#       per the stage-1 baseline manifest.
#   vendor-boot.img : SHA256
#       4f2bbfb25d0255a81ce8a7f18420a138c8225992574e06bf5d30176034fc4b92
#   defconfig : the board-validated stage-6 configuration
#       (CONFIG_CMDLINE_FORCE with mcs_reserve_cpus=4-5 appended to the vendor
#       cmdline; all other present CPUs remain available to Linux).
#   The in-tree tl3572-evm.dts edits from the manual stage-4 session are
#   intentionally NOT applied: the validated DTB is built from the vendor DTB
#   plus the overlay below.

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI = " \
    file://linux-6.12.69-v1.0-gf1b67c2.tar.gz \
    file://0001-arm64-smp-reserve-SGI-for-mcs-km.patch \
    file://0002-cpu-reserve-selected-cpus-for-mcs.patch \
    file://0004-arm64-mcs-add-second-reserved-sgi.patch \
    file://defconfig \
    file://localversion \
    file://vendor-boot.img \
    file://tl3572-mcs-overlay.dts \
    file://boot-mcs.its \
    file://mcs_km.c;subdir=mcs-km \
    file://Makefile;subdir=mcs-km \
"

S = "${WORKDIR}/linux-6.12.69-v1.0-gf1b67c2"
B = "${S}"

# The vendor kernel (and the board-validated stage-4 Image) is built with the
# Arm GNU toolchain 14.3.1; the Yocto external-openeuler GCC 12.3 toolchain
# must not silently replace it.
TL3572_VENDOR_TOOLCHAIN ?= "/home/openeuler/build/tl3572-2oo3/toolchain-14.3"
TL3572_CROSS_COMPILE = "aarch64-none-linux-gnu-"

DEPENDS = "dtc-native u-boot-tools-native"

# Pinned reference hashes (the final boot.img also embeds build timestamps).
TL3572_VENDOR_DTB_SHA256 = "ae073a93320bf4d5e5a9016aa3396ef4deeb6c3ecdf839f28f337404e0c4737f"
TL3572_RESOURCE_SHA256 = "7508f47d084c56cac9b92fc44ae5dc4c4c74bb481d2860ac52d7cd10bd520269"
TL3572_MCS_FDT_SHA256 = "9b74be5ea7a8f39846d788ccc8fb5472d15288eed7f9e8347846422710c426e0"
TL3572_KO_VERMAGIC = "6.12.69-gf1b67c293213 SMP mod_unload aarch64"

tl3572_assert_sha256() {
    want="$1"
    file="$2"
    got=$(sha256sum "$file" | awk '{print $1}')
    if [ "$got" != "$want" ]; then
        bbfatal "tl3572: $file sha256 $got does not match pinned $want"
    fi
}

do_configure() {
    cd ${S}
    install -m 0644 ${WORKDIR}/localversion ${S}/localversion
    install -m 0644 ${WORKDIR}/defconfig ${S}/.config
    export PATH="${TL3572_VENDOR_TOOLCHAIN}/bin:${PATH}"
    export ARCH="arm64"
    export CROSS_COMPILE="${TL3572_CROSS_COMPILE}"
    make olddefconfig < /dev/null
    grep -q '^CONFIG_CMDLINE_FORCE=y' .config || bbfatal "CONFIG_CMDLINE_FORCE lost"
    grep -q '^CONFIG_REMOTEPROC=y' .config || bbfatal "CONFIG_REMOTEPROC lost"
    grep -q '^CONFIG_RPMSG_CHAR=y' .config || bbfatal "CONFIG_RPMSG_CHAR lost"
    grep -q 'mcs_reserve_cpus=4-5' .config || bbfatal "MCS CPU4-5 reservation lost"
    if grep -q 'maxcpus=' .config; then
        bbfatal "legacy maxcpus policy must not be present"
    fi
}

do_compile() {
    cd ${S}
    export PATH="${TL3572_VENDOR_TOOLCHAIN}/bin:${PATH}"
    export ARCH="arm64"
    export CROSS_COMPILE="${TL3572_CROSS_COMPILE}"

    # Image plus in-tree modules so that Module.symvers exists for the
    # external mcs_km build (mirrors the validated manual build).
    make ${PARALLEL_MAKE} Image modules < /dev/null
    grep -q '6\.12\.69-gf1b67c293213' include/generated/utsrelease.h \
        || bbfatal "utsrelease mismatch"

    # mcs_km against the freshly built tree.  The vendor kbuild machinery
    # automatically links scripts/module-common.o into external modules.
    make ${PARALLEL_MAKE} -C ${S} M=${WORKDIR}/mcs-km modules < /dev/null
    grep -aq "vermagic=${TL3572_KO_VERMAGIC}" ${WORKDIR}/mcs-km/mcs_km.ko || bbfatal "mcs_km vermagic does not match ${TL3572_KO_VERMAGIC}"

    # Vendor blobs from the pinned vendor boot image.
    cd ${WORKDIR}
    dumpimage -T flat_dt -p 0 -o vendor.dtb vendor-boot.img
    dumpimage -T flat_dt -p 2 -o resource vendor-boot.img
    tl3572_assert_sha256 "${TL3572_VENDOR_DTB_SHA256}" vendor.dtb
    tl3572_assert_sha256 "${TL3572_RESOURCE_SHA256}" resource

    # Board-validated MCS DTB: vendor DTB + overlay (mcs-rmem, mcs-remoteproc,
    # unused UFS controller disabled).
    dtc -@ -I dts -O dtb -o tl3572-mcs.dtbo tl3572-mcs-overlay.dts
    fdtoverlay -i vendor.dtb -o fdt tl3572-mcs.dtbo
    tl3572_assert_sha256 "${TL3572_MCS_FDT_SHA256}" fdt

    # Rockchip external-data FIT (header 0x600, first data at 0x800).
    ln -sf ${S}/arch/arm64/boot/Image kernel
    mkimage -f boot-mcs.its -B 0x200 -E -p 0x800 boot.img
    dumpimage -l boot.img > boot.img.dumpimage.txt
    grep -q "${TL3572_MCS_FDT_SHA256}" boot.img.dumpimage.txt \
        || bbfatal "FIT fdt hash mismatch"
    grep -q "${TL3572_RESOURCE_SHA256}" boot.img.dumpimage.txt \
        || bbfatal "FIT resource hash mismatch"
}

do_install() {
    install -d ${D}/lib/modules
    install -m 0644 ${WORKDIR}/mcs-km/mcs_km.ko ${D}/lib/modules/mcs_km.ko
}

FILES:${PN} += "/lib/modules"
INHIBIT_PACKAGE_STRIP = "1"
INSANE_SKIP:${PN} += "already-stripped"

do_deploy() {
    install -m 0644 ${S}/arch/arm64/boot/Image \
        ${DEPLOYDIR}/Image-tl3572-6.12.69-gf1b67c293213
    install -m 0644 ${WORKDIR}/boot.img ${DEPLOYDIR}/boot-tl3572-openeuler-mcs.img
    install -m 0644 ${WORKDIR}/boot.img.dumpimage.txt \
        ${DEPLOYDIR}/boot-tl3572-openeuler-mcs.img.dumpimage.txt
    install -m 0644 ${S}/.config ${DEPLOYDIR}/tl3572-6.12.69.config
    install -m 0644 ${WORKDIR}/mcs-km/mcs_km.ko ${DEPLOYDIR}/mcs_km-tl3572.ko
    cd ${DEPLOYDIR}
    sha256sum Image-tl3572-6.12.69-gf1b67c293213 boot-tl3572-openeuler-mcs.img \
        tl3572-6.12.69.config mcs_km-tl3572.ko > SHA256SUMS.tl3572-kernel
}
addtask deploy after do_compile before do_build

#!/bin/bash
# Stage4 Yocto-ization: build the linux-tl3572 recipe + layer files
set -euo pipefail
WS=/home/openeuler/build/tl3572-2oo3
K=$WS/build-kernel
P=$WS/kernel-src-pristine
L=$WS/meta-tl3572-stage3
RD=$L/recipes-kernel/linux
F=$RD/files
V3=$WS/bootimg-out-stage4-external-fit-v3

mkdir -p "$F"

echo ====STEP1_REPACKAGE_TARBALL
if [ ! -f $F/linux-6.12.69-v1.0-gf1b67c2.tar.gz ]; then
  rm -rf $WS/layer-staging
  mkdir -p $WS/layer-staging/linux-6.12.69-v1.0-gf1b67c2
  (cd $P && tar cf - --exclude=.git .) | (cd $WS/layer-staging/linux-6.12.69-v1.0-gf1b67c2 && tar xf -)
  diff -rq $P $WS/layer-staging/linux-6.12.69-v1.0-gf1b67c2 --exclude=.git >/dev/null && echo ROUNDTRIP_OK || { echo ROUNDTRIP_MISMATCH; exit 1; }
  (cd $WS/layer-staging && tar czf $F/linux-6.12.69-v1.0-gf1b67c2.tar.gz linux-6.12.69-v1.0-gf1b67c2)
fi
ls -la $F/linux-6.12.69-v1.0-gf1b67c2.tar.gz

echo ====STEP2_0001_PATCH
{
  diff -u $P/arch/arm64/kernel/smp.c $K/arch/arm64/kernel/smp.c \
    | sed -e '1s|^--- .*|--- a/arch/arm64/kernel/smp.c|' -e '2s|^+++ .*|+++ b/arch/arm64/kernel/smp.c|' || true
  diff -u $P/arch/arm64/include/asm/smp.h $K/arch/arm64/include/asm/smp.h \
    | sed -e '1s|^--- .*|--- a/arch/arm64/include/asm/smp.h|' -e '2s|^+++ .*|+++ b/arch/arm64/include/asm/smp.h|' || true
} > $F/0001-arm64-smp-reserve-SGI-for-mcs-km.patch
[ -s $F/0001-arm64-smp-reserve-SGI-for-mcs-km.patch ] || { echo EMPTY_PATCH; exit 1; }
(cd $P && patch -p1 --dry-run < $F/0001-arm64-smp-reserve-SGI-for-mcs-km.patch) && echo PATCH_DRYRUN_OK
wc -l $F/0001-arm64-smp-reserve-SGI-for-mcs-km.patch

echo ====STEP3_VENDOR_BLOBS_AND_SOURCES
cp -f /home/openeuler/vendor-boot.img $F/vendor-boot.img
cp -f $K/.config $F/defconfig
cp -f $WS/mcs-km-tl3572/mcs_km.c $F/mcs_km.c
cp -f $WS/mcs-km-tl3572/Makefile $F/mcs-km-Makefile
diff -u $WS/src/mcs/mcs_km/mcs_km.c $WS/mcs-km-tl3572/mcs_km.c \
  | sed -e '1s|^--- .*|--- a/mcs_km.c (openEuler mcs 5cb4915)|' -e '2s|^+++ .*|+++ b/mcs_km.c (TL3572 of-cpu adaptation)|' \
  > $F/0003-mcs-km-of-cpu-adaptation.patch || true
printf '%s\n' '-gf1b67c293213' > $F/localversion

echo ====STEP4_OVERLAY_DTS
cat > $F/tl3572-mcs-overlay.dts <<'DTSEOF'
/dts-v1/;
/plugin/;

/ {
	fragment@0 {
		target-path = "/reserved-memory";

		__overlay__ {
			mcs_rmem: mcs-rmem@134000000 {
				reg = <0x1 0x34000000 0x0 0x04000000>;
				no-map;
			};
		};
	};

	fragment@1 {
		target-path = "/";

		__overlay__ {
			mcs-remoteproc {
				compatible = "oe,mcs_remoteproc";
				memory-region = <&mcs_rmem>;
				status = "okay";
			};
		};
	};

	fragment@2 {
		target-path = "/soc/ufs@29e00000";

		__overlay__ {
			status = "disabled";
		};
	};
};
DTSEOF

echo ====STEP5_ITS
cat > $F/boot-mcs.its <<'ITSEOF'
/*
 * Copyright (C) 2021 Rockchip Electronics Co., Ltd.
 *
 * SPDX-License-Identifier: GPL-2.0
 */

/dts-v1/;
/ {
    description = "FIT image with Linux kernel, FDT blob and resource";

    images {
        fdt {
            data = /incbin/("fdt");
            type = "flat_dt";
            arch = "arm64";
            compression = "none";
            load = <0xffffff00>;

            hash {
                algo = "sha256";
            };
        };

        kernel {
            data = /incbin/("kernel");
            type = "kernel";
            arch = "arm64";
            os = "linux";
            compression = "none";
            entry = <0xffffff01>;
            load = <0xffffff01>;

            hash {
                algo = "sha256";
            };
        };

        resource {
            data = /incbin/("resource");
            type = "multi";
            arch = "arm64";
            compression = "none";

            hash {
                algo = "sha256";
            };
        };
    };

    configurations {
        default = "conf";

        conf {
            rollback-index = <0x00>;
            fdt = "fdt";
            kernel = "kernel";
            multi = "resource";

            signature {
                algo = "sha256,rsa2048";
                padding = "pss";
                key-name-hint = "dev";
                sign-images = "fdt", "kernel", "multi";
            };
        };
    };
};
ITSEOF

echo ====STEP6_RECIPE
cat > $RD/linux-tl3572_6.12.69.bb <<'BBEOF'
SUMMARY = "TL3572 vendor Linux 6.12.69 with openEuler MICA/MCS enablement (stage 4)"
DESCRIPTION = "Rebuilds the board-validated stage-4 kernel with the Arm GNU 14.3 \
vendor toolchain (reserved-SGI exports for mcs_km, vendor cmdline plus maxcpus=7), \
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
#   defconfig : the board-validated stage-4 v4 configuration
#       (CONFIG_CMDLINE_FORCE with maxcpus=7 appended to the vendor cmdline).
#   The in-tree tl3572-evm.dts edits from the manual stage-4 session are
#   intentionally NOT applied: the validated DTB is built from the vendor DTB
#   plus the overlay below.

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI = " \
    file://linux-6.12.69-v1.0-gf1b67c2.tar.gz \
    file://0001-arm64-smp-reserve-SGI-for-mcs-km.patch \
    file://defconfig \
    file://localversion \
    file://vendor-boot.img \
    file://tl3572-mcs-overlay.dts \
    file://boot-mcs.its \
    file://mcs_km.c;subdir=mcs-km \
    file://mcs-km-Makefile;subdir=mcs-km \
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
TL3572_MCS_FDT_SHA256 = "195535ebebee247d99cda7596dbb62094a7465a24a2774df975a58133edcd0fe"
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
    grep -q 'maxcpus=7' .config || bbfatal "maxcpus=7 lost"
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
    vm=$(grep -ao 'vermagic=[^ ]* [^ ]* [^ ]* [^ ]*' ${WORKDIR}/mcs-km/mcs_km.ko | head -1 | cut -d= -f2-)
    if [ "$vm" != "${TL3572_KO_VERMAGIC}" ]; then
        bbfatal "mcs_km vermagic '$vm' != '${TL3572_KO_VERMAGIC}'"
    fi

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
BBEOF

echo ====STEP7_IMAGE_RECIPE_PATCH
python3 - <<'PYEOF'
p = "/home/openeuler/build/tl3572-2oo3/meta-tl3572-stage3/recipes-core/images/tl3572-openeuler-mcs-image.bb"
s = open(p).read()
anchor = "    mcsctl \\\n    screen \\"
addition = "    mcsctl \\\n    linux-tl3572 \\\n    screen \\"
assert s.count(anchor) == 1, "anchor not found exactly once"
assert "linux-tl3572" not in s, "already patched"
open(p, "w").write(s.replace(anchor, addition, 1))
print("IMAGE_RECIPE_PATCHED")
PYEOF
grep -n "linux-tl3572" $L/recipes-core/images/tl3572-openeuler-mcs-image.bb

echo ====STEP8_BUILD_SCRIPT
sed 's/stage3-m2/stage4/g' $WS/remote-build-stage3-m2.sh > $WS/remote-build-stage4.sh
chmod +x $WS/remote-build-stage4.sh
grep -E "log=|status=" $WS/remote-build-stage4.sh

echo ====STEP9_FINAL_LISTING
ls -la $RD $F
sha256sum $F/vendor-boot.img $F/defconfig $F/mcs_km.c $F/mcs-km-Makefile
echo ====SETUP_DONE

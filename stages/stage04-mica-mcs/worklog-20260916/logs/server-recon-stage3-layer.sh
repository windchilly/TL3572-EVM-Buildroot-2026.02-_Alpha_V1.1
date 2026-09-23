#!/bin/bash
# Stage4 Yocto-ization recon: meta-tl3572-stage3 layer + build site
WS=/home/openeuler/build/tl3572-2oo3
L=$WS/meta-tl3572-stage3

echo ====LAYER_TREE
find $L -type f | sort

echo ====LAYER_CONF
cat $L/conf/layer.conf 2>/dev/null

echo ====MACHINE_CONF
for f in $L/conf/machine/*.conf; do echo "--- $f"; cat "$f"; done

echo ====IMAGE_RECIPES
find $L -name "*.bb" -path "*image*" | while read f; do echo "--- $f"; cat "$f"; done

echo ====ALL_BBAPPEND_AND_CLASSES
find $L -name "*.bbappend" -o -name "*.bbclass" | sort

echo ====BBLAYERS
find $WS -maxdepth 4 -name bblayers.conf 2>/dev/null | while read f; do echo "--- $f"; grep -v "^#" "$f" | grep -v "^$"; done

echo ====LOCAL_CONF_ACTIVE
find $WS -maxdepth 4 -name local.conf 2>/dev/null | while read f; do echo "--- $f"; grep -v "^#" "$f" | grep -v "^$" | head -40; done

echo ====BUILD_SCRIPTS
ls -la $WS/*.sh 2>/dev/null

echo ====VENDOR_TARBALL
find $WS -maxdepth 2 -iname "*linux-6.12*" -not -path "*/build-kernel/*" 2>/dev/null | head

echo ====V3_ASSETS
ls -la $WS/bootimg-out-stage4-external-fit-v3/ 2>/dev/null

echo ====OE_MCS_RECIPES
find $WS/src/yocto-meta-openeuler -name "*.bb*" 2>/dev/null | grep -i mcs | head -20

echo ====VENDOR_BOOT_IMG
ls -la /home/openeuler/vendor-boot.img 2>/dev/null
sha256sum /home/openeuler/vendor-boot.img 2>/dev/null

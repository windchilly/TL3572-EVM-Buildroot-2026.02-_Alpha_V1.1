#!/bin/bash
# Stage4 v4: CONFIG_CMDLINE_FORCE maxcpus=7 + incremental Image rebuild + FIT v4 assembly
set -eo pipefail
WS=/home/openeuler/build/tl3572-2oo3
K=$WS/build-kernel
V3=$WS/bootimg-out-stage4-external-fit-v3
V4=$WS/bootimg-out-stage4-external-fit-v4-maxcpus
mkdir -p "$WS/logs"
MLOG=$WS/logs/stage4-v4-make.log

cd "$K"
export PATH="$WS/toolchain-14.3/bin:$PATH"
export ARCH=arm64
export CROSS_COMPILE=aarch64-none-linux-gnu-

echo ====STEP1_CONFIG
cp -f .config "$K/.config.pre-maxcpus-20260916"
scripts/config --set-str CMDLINE "storagemedia=emmc androidboot.storagemedia=emmc androidboot.mode=normal androidboot.verifiedbootstate=orange rw rootwait earlycon=uart8250,mmio32,0x2c130000 console=ttyFIQ0 root=/dev/mmcblk0p6 rcupdate.rcu_expedited=1 rcu_nocbs=all maxcpus=7"
scripts/config -e CMDLINE_FORCE
scripts/config -d CMDLINE_FROM_BOOTLOADER
make olddefconfig < /dev/null
grep -E '^CONFIG_CMDLINE|^# CONFIG_CMDLINE' .config

echo ====STEP2_BUILD_IMAGE
make Image -j32 < /dev/null > "$MLOG" 2>&1 || { echo MAKE_FAILED; tail -40 "$MLOG"; exit 1; }
tail -3 "$MLOG"
ls -la "$K/arch/arm64/boot/Image"
grep -o '6\.12\.69[^"]*' "$K/include/generated/utsrelease.h"

echo ====STEP3_ASSEMBLE_V4
rm -rf "$V4"; mkdir -p "$V4"
cp "$V3/fdt" "$V3/resource" "$V4/"
ITS=$(ls "$V3"/*.its | head -1)
cp "$ITS" "$V4/boot-mcs-tl3572-external-fit-v4-maxcpus.its"
ln -sf "$K/arch/arm64/boot/Image" "$V4/kernel"
cp -f "$K/.config" "$V4/kernel-config-v4-maxcpus"
diff -u "$K/.config.pre-maxcpus-20260916" "$K/.config" > "$V4/config-diff.txt" || true
cd "$V4"
mkimage -f boot-mcs-tl3572-external-fit-v4-maxcpus.its -B 0x200 -E -p 0x800 boot.img 2>&1 | tee mkimage.log

echo ====STEP4_VALIDATE
dumpimage -l boot.img > dumpimage.txt 2>&1
head -30 dumpimage.txt
{
  echo "STAGE4_EXTERNAL_FIT_V4_MAXCPUS_VALIDATION=PASS"
  echo "kernel_sha256=$(sha256sum kernel | awk '{print $1}')"
  echo "fdt_sha256=$(sha256sum fdt | awk '{print $1}')"
  echo "resource_sha256=$(sha256sum resource | awk '{print $1}')"
  echo "bootimg_sha256=$(sha256sum boot.img | awk '{print $1}')"
  echo "cmdline_policy=CONFIG_CMDLINE_FORCE vendor_cmdline_plus_maxcpus=7"
} > validation.txt
sha256sum boot.img fdt resource kernel > SHA256SUMS
gzip -9 -k -f boot.img
cat validation.txt
ls -la
echo ====ALL_DONE

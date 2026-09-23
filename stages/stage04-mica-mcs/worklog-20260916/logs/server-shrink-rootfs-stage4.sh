#!/bin/bash
# Stage4: shrink the freshly built rootfs.ext4 below the RKFW u32 firmware limit
set -euo pipefail
WS=/home/openeuler/build/tl3572-2oo3
DEPLOY=$WS/build/build-tl3572/tmp/deploy/images/tl3572-evm

echo ====DEPLOY_LISTING
ls -lat $DEPLOY/*.rootfs.ext4 2>/dev/null | head -5
NEWEST=$(ls -t $DEPLOY/*.rootfs.ext4 | head -1)
echo "NEWEST=$NEWEST"

echo ====COPY
rm -f $WS/stage4-rootfs-shrunk.ext4
cp -f "$NEWEST" $WS/stage4-rootfs-shrunk.ext4

echo ====E2FSCK_PRE
e2fsck -fn $WS/stage4-rootfs-shrunk.ext4 2>&1 | tail -5

echo ====RESIZE
resize2fs $WS/stage4-rootfs-shrunk.ext4 3906248K 2>&1 | tail -3

echo ====E2FSCK_POST
e2fsck -fn $WS/stage4-rootfs-shrunk.ext4 2>&1 | tail -5

echo ====FINAL
ls -la $WS/stage4-rootfs-shrunk.ext4
sha256sum $WS/stage4-rootfs-shrunk.ext4
echo ====SHRINK_DONE

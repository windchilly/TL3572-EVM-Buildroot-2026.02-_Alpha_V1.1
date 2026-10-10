#!/usr/bin/env bash
# Compile EDRV and real BSP together without exposing a POWERLINK run command.
# No image is copied into formal firmware/ and nothing is deployed to a board.
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly uni=${UNIPROTON_ROOT:?Set a NEW candidate UNIPROTON_ROOT}
readonly upstream=${OPLK_SOURCE:?Set the prepared pinned OPLK_SOURCE}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
test -f "$upstream/stack/include/oplk/targetsystem.h"
UNIPROTON_ROOT="$uni" bash "$stage_root/build/prepare_m7_integrated.sh"
readonly app="$uni/demos/rk3572_mica/apps/openamp"
mkdir "$app/powerlink-port" "$app/powerlink-upstream"
for source in edrv-rk3572.c m7_edrv.h m7_eth2_hw.h oplkcfg.h; do
    install -m 0644 "$stage_root/source/powerlink/port/$source" "$app/powerlink-port/$source"
done
cp -a "$stage_root/source/powerlink/port/oplk" "$app/powerlink-port/oplk"
mkdir "$app/powerlink-upstream/stack" "$app/powerlink-upstream/contrib"
cp -a "$upstream/stack/include" "$app/powerlink-upstream/stack/include"
cp -a "$upstream/contrib/trace" "$app/powerlink-upstream/contrib/trace"
git -C "$uni" apply --check "$stage_root/source/patches/uniproton/0011-rk3572-powerlink-edrv-dormant.patch"
git -C "$uni" apply "$stage_root/source/patches/uniproton/0011-rk3572-powerlink-edrv-dormant.patch"
readonly demo="$uni/demos/rk3572_mica"
for name in up-a up-b; do
    if [[ "$name" == up-a ]]; then cpu=4; sgi=8; image=0x7b200000; mmu=0x7ba00000
    else cpu=5; sgi=9; image=0x7c200000; mmu=0x7ca00000; fi
    build="$demo/build/m7-powerlink-p1-$name"
    cmake -S "$demo" -B "$build" -DAPP:STRING=rk3572_mica -DTOOLCHAIN_PATH:STRING="$toolchain" \
        -DMCS_CLIENT_CPU_ID:STRING="$cpu" -DMCS_NOTIFY_SGI_ID:STRING="$sgi" \
        -DMCS_IMAGE_ADDR:STRING="$image" -DMCS_MMU_ADDR:STRING="$mmu" \
        -DM7_CAN_DIRECT_TEST:BOOL=OFF -DM7_CAN_IRQ_TEST:BOOL=OFF \
        -DM7_INTEGRATED_FIRMWARE:BOOL=ON -DM7_POWERLINK_EDRV:BOOL=ON
    cmake --build "$build" --target rk3572_mica --parallel
    cp "$build/rk3572_mica" "$demo/build/tl3572-m7-integrated-$name.elf"
    "$toolchain/bin/aarch64-none-elf-objcopy" -O binary "$build/rk3572_mica" "$demo/build/$name.runtime.bin"
    sha256sum "$demo/build/tl3572-m7-integrated-$name.elf"
    sha256sum "$demo/build/$name.runtime.bin"
done
python3 "$stage_root/tests/audit_integrated_mmu.py" --firmware-dir "$demo/build"
python3 "$stage_root/tests/verify_integrated_elf.py" --firmware-dir "$demo/build"
# Force the dormant EDRV+BSP objects into a relocatable file: --gc-sections would
# otherwise remove unreferenced EDRV at the final firmware link. This is NOT MN.
readonly objects="$demo/build/m7-powerlink-p1-up-b/apps/openamp/CMakeFiles/rpmsg.dir"
"$toolchain/bin/aarch64-none-elf-ld" -r "$objects/rk3572_eth_test.c.o" \
    "$objects/powerlink-port/edrv-rk3572.c.o" -o "$demo/build/edrv-with-real-bsp.o"
"$toolchain/bin/aarch64-none-elf-nm" -u "$demo/build/edrv-with-real-bsp.o"
python3 "$stage_root/tests/audit_powerlink_bsp.py" "$demo/build/edrv-with-real-bsp.o" "$toolchain"
echo 'CUMULATIVE CANDIDATE COMPILE PASS; dormant EDRV, no MN runtime, no board acceptance'

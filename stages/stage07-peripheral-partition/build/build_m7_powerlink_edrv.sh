#!/usr/bin/env bash
# P1 software baseline only. No deployment, PHY access or network transmission.
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly project_root=${TL3572_PROJECT:-/home/openeuler/build/tl3572-2oo3}
readonly output=${POWERLINK_BUILD_ROOT:-$project_root/build-powerlink-mn-p1}
export TOOLCHAIN_PATH=${TOOLCHAIN_PATH:-$project_root/toolchain-14.3}
test ! -e "$output" || { echo "Choose a fresh POWERLINK_BUILD_ROOT: $output" >&2; exit 1; }
POWERLINK_BUILD_ROOT="$output/core" bash "$stage_root/build/build_m7_powerlink_core.sh"
readonly source_tree="$output/core/source/openPOWERLINK_V2-2.7.2"
readonly port="$stage_root/source/powerlink/port"
cmake -S "$port/edrv" -B "$output/edrv-native" -DOPLK_SOURCE="$source_tree" -DCMAKE_BUILD_TYPE=Release
cmake --build "$output/edrv-native" --parallel
ctest --test-dir "$output/edrv-native" --verbose --output-on-failure
cmake -S "$port/edrv" -B "$output/edrv-aarch64" -DOPLK_SOURCE="$source_tree" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DCMAKE_TOOLCHAIN_FILE="$port/aarch64-none-elf.cmake"
cmake --build "$output/edrv-aarch64" --parallel
"$TOOLCHAIN_PATH/bin/aarch64-none-elf-ld" -r --whole-archive \
    "$output/core/aarch64/libm7_powerlink_mn_core.a" \
    "$output/edrv-aarch64/libm7_powerlink_eth2_edrv.a" --no-whole-archive \
    -o "$output/mn-core-edrv.o"
python3 "$stage_root/tests/audit_powerlink_edrv.py" "$output" "$TOOLCHAIN_PATH"
echo 'P1 EDRV SOFTWARE BUILD COMPLETE (BSP/target/timer unresolved; NOT runnable MN / NOT board acceptance)'

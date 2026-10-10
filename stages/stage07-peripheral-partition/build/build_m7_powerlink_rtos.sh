#!/usr/bin/env bash
# P2 software only: no deployment, timer registers, PHY or network access.
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly project_root=${TL3572_PROJECT:-/home/openeuler/build/tl3572-2oo3}
readonly output=${POWERLINK_BUILD_ROOT:-$project_root/build-powerlink-mn-p2}
export TOOLCHAIN_PATH=${TOOLCHAIN_PATH:-$project_root/toolchain-14.3}
test ! -e "$output" || { echo "Choose a fresh POWERLINK_BUILD_ROOT: $output" >&2; exit 1; }
POWERLINK_BUILD_ROOT="$output/p1" bash "$stage_root/build/build_m7_powerlink_edrv.sh"
readonly source_tree="$output/p1/core/source/openPOWERLINK_V2-2.7.2"
readonly port="$stage_root/source/powerlink/port"
cmake -S "$port/rtos" -B "$output/rtos-native" -DOPLK_SOURCE="$source_tree" -DCMAKE_BUILD_TYPE=Release
cmake --build "$output/rtos-native" --parallel
ctest --test-dir "$output/rtos-native" --verbose --output-on-failure
cmake -S "$port/rtos" -B "$output/rtos-aarch64" -DOPLK_SOURCE="$source_tree" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DCMAKE_TOOLCHAIN_FILE="$port/aarch64-none-elf.cmake"
cmake --build "$output/rtos-aarch64" --parallel
"$TOOLCHAIN_PATH/bin/aarch64-none-elf-ld" -r --whole-archive \
    "$output/p1/core/aarch64/libm7_powerlink_mn_core.a" \
    "$output/p1/edrv-aarch64/libm7_powerlink_eth2_edrv.a" \
    "$output/rtos-aarch64/libm7_powerlink_rtos.a" --no-whole-archive -o "$output/mn-core-edrv-rtos.o"
python3 "$stage_root/tests/audit_powerlink_rtos.py" "$output" "$TOOLCHAIN_PATH"
echo 'P2 SOFTWARE BUILD COMPLETE (real BSP unresolved; NOT MN runtime / board acceptance)'

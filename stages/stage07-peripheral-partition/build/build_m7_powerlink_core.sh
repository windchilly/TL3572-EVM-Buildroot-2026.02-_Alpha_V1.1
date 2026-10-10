#!/usr/bin/env bash
# P0 only: native unit test and AArch64 static library, never deploy or transmit.
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly project_root=${TL3572_PROJECT:-/home/openeuler/build/tl3572-2oo3}
readonly output=${POWERLINK_BUILD_ROOT:-$project_root/build-powerlink-mn-p0}
export TOOLCHAIN_PATH=${TOOLCHAIN_PATH:-$project_root/toolchain-14.3}
test ! -e "$output" || { echo "Choose a fresh POWERLINK_BUILD_ROOT: $output" >&2; exit 1; }
python3 "$stage_root/build/prepare_m7_powerlink.py" "$output/source"
readonly source_tree="$output/source/openPOWERLINK_V2-2.7.2"
readonly port="$stage_root/source/powerlink/port"
cmake --version
"$TOOLCHAIN_PATH/bin/aarch64-none-elf-gcc" --version
cmake -S "$port" -B "$output/native" -DOPLK_SOURCE="$source_tree" -DCMAKE_BUILD_TYPE=Release
cmake --build "$output/native" --parallel
ctest --test-dir "$output/native" --verbose --output-on-failure
cmake -S "$port" -B "$output/aarch64" -DOPLK_SOURCE="$source_tree" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DCMAKE_TOOLCHAIN_FILE="$port/aarch64-none-elf.cmake"
cmake --build "$output/aarch64" --parallel
# Merge every member to expose the real unresolved HAL, not per-object references.
"$TOOLCHAIN_PATH/bin/aarch64-none-elf-ld" -r --whole-archive \
    "$output/aarch64/libm7_powerlink_mn_core.a" --no-whole-archive -o "$output/aarch64/mn-core.o"
"$TOOLCHAIN_PATH/bin/aarch64-none-elf-readelf" -h "$output/aarch64/mn-core.o"
"$TOOLCHAIN_PATH/bin/aarch64-none-elf-nm" -u "$output/aarch64/mn-core.o"
sha256sum "$output/aarch64/libm7_powerlink_mn_core.a"
python3 "$stage_root/tests/audit_powerlink_core.py" "$output" "$TOOLCHAIN_PATH"
echo 'P0 CORE BUILD COMPLETE (HAL unresolved; NOT runnable firmware / NOT board acceptance)'

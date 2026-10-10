#!/usr/bin/env bash
# P3a real full-stack software integration. No board access or deployment.
set -euo pipefail
readonly stage_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly project_root=${TL3572_PROJECT:-/home/openeuler/build/tl3572-2oo3}
readonly output=${POWERLINK_BUILD_ROOT:-$project_root/build-powerlink-mn-p3a}
export TOOLCHAIN_PATH=${TOOLCHAIN_PATH:-$project_root/toolchain-14.3}
test ! -e "$output" || { echo "Choose a fresh POWERLINK_BUILD_ROOT: $output" >&2; exit 1; }
POWERLINK_BUILD_ROOT="$output/p2" bash "$stage_root/build/build_m7_powerlink_rtos.sh"
python3 "$stage_root/build/prepare_m7_powerlink.py" "$output/source"
readonly source_tree="$output/source/openPOWERLINK_V2-2.7.2"
readonly port="$stage_root/source/powerlink/port"
for patch in 0003-uniproton-passive-lifecycle.patch 0004-uniproton-od-prc-disabled.patch \
             0005-mn-request-queue-allocation-errors.patch; do
    GIT_CEILING_DIRECTORIES="$output/source" git -C "$source_tree" apply --ignore-space-change --check "$port/$patch"
    GIT_CEILING_DIRECTORIES="$output/source" git -C "$source_tree" apply --ignore-space-change "$port/$patch"
done
for kind in native aarch64; do
    options=()
    if [[ "$kind" == aarch64 ]]; then options+=("-DCMAKE_TOOLCHAIN_FILE=$port/aarch64-none-elf.cmake"); fi
    cmake -S "$port/mn" -B "$output/$kind" -DOPLK_SOURCE="$source_tree" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON "${options[@]}"
    cmake --build "$output/$kind" --parallel
    if [[ "$kind" == native ]]; then ctest --test-dir "$output/$kind" --verbose --output-on-failure; fi
done
"$TOOLCHAIN_PATH/bin/aarch64-none-elf-ld" -r --whole-archive \
    "$output/aarch64/core/libm7_powerlink_mn_core.a" \
    "$output/aarch64/libm7_powerlink_passive_mn.a" --no-whole-archive -o "$output/mn-passive-full.o"
python3 "$stage_root/tests/audit_powerlink_passive_mn.py" "$output" "$TOOLCHAIN_PATH"
echo 'P3a FULL STACK SOFTWARE PASS; no RTOS owner task/candidate deployment/hardware acceptance'

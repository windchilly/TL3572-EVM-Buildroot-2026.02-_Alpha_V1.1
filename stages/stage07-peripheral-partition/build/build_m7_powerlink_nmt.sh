#!/usr/bin/env bash
# P3g fresh full software build, UniProton-only direct PDO setup error fix.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly output=${POWERLINK_BUILD_ROOT:?Set a NEW full software root}
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
export TOOLCHAIN_PATH="$toolchain"
bash "$stage/build/build_m7_powerlink_passive_mn.sh"
readonly tree="$output/source/openPOWERLINK_V2-2.7.2"
for patch in "$stage/source/powerlink/port/0006-uniproton-pdo-setup-no-wait.patch" \
             "$stage/source/powerlink/port/0007-uniproton-cyclic-allocation-guards.patch"; do
    GIT_CEILING_DIRECTORIES="$output/source" git -C "$tree" apply --ignore-space-change --check "$patch"
    GIT_CEILING_DIRECTORIES="$output/source" git -C "$tree" apply --ignore-space-change "$patch"
done
for kind in native aarch64; do
    cmake --build "$output/$kind" --parallel
    if [[ "$kind" == native ]]; then ctest --test-dir "$output/$kind" --verbose --output-on-failure; fi
done
"$toolchain/bin/aarch64-none-elf-ld" -r --whole-archive \
    "$output/aarch64/core/libm7_powerlink_mn_core.a" \
    "$output/aarch64/libm7_powerlink_passive_mn.a" --no-whole-archive -o "$output/mn-passive-full.o"
python3 "$stage/tests/audit_powerlink_passive_mn.py" "$output" "$toolchain"
echo 'P3g full core rebuilt, direct PDO errors/no wait fix applied; SOFTWARE ONLY'

#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 2 ]]; then
    echo "Usage: bash verify_m7_integrated_repro.sh FIRST_BUILD_DIR SECOND_BUILD_DIR" >&2; exit 1
fi
readonly toolchain=${TOOLCHAIN_PATH:-/home/openeuler/build/tl3572-2oo3/toolchain-14.3}
readonly task_out=$(mktemp -d /tmp/tl3572-integrated-repro.XXXXXX)
echo "Comparison outputs: $task_out"
for task_up in up-a up-b; do
    task_name="tl3572-m7-integrated-$task_up"
    for task_index in 1 2; do
        "$toolchain/bin/aarch64-none-elf-objcopy" -O binary "${!task_index}/$task_name.elf" "$task_out/$task_name-$task_index.bin"
        sha256sum "$task_out/$task_name-$task_index.bin"
    done
    cmp "$task_out/$task_name-1.bin" "$task_out/$task_name-2.bin"
    echo "RUNTIME IMAGE REPRO PASS $task_name"
done

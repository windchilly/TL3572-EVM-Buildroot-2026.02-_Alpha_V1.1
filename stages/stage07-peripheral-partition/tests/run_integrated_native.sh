#!/usr/bin/env bash
set -euo pipefail
task_stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
task_app="$task_stage/source/overlay/uniproton/demos/rk3572_mica/apps/openamp"
task_out=$(mktemp -d /tmp/tl3572-integrated-native.XXXXXX)
echo "Native outputs: $task_out"
gcc -std=c11 -O2 -Wall -Wextra -Werror -I "$task_app" "$task_stage/tests/test_integrated_command.c" -o "$task_out/test-command"
"$task_out/test-command"
for task_cpu in 4 5; do
    gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID="$task_cpu" \
        -I "$task_stage/tests/integrated-stubs" -I "$task_app" \
        "$task_app/rk3572_integrated.c" "$task_stage/tests/test_integrated_dispatch.c" -o "$task_out/test-dispatch-$task_cpu"
    "$task_out/test-dispatch-$task_cpu"
    for task_fail in 1 2 3 4; do
        "$task_out/test-dispatch-$task_cpu" create "$task_fail"
        "$task_out/test-dispatch-$task_cpu" resume "$task_fail"
    done
done
for task_codec in test_rs232_codec test_can_fd_codec; do
    gcc -std=c11 -O2 -Wall -Wextra -Werror -I "$task_app" "$task_stage/tests/$task_codec.c" -o "$task_out/$task_codec"
    "$task_out/$task_codec"
done
gcc -std=c11 -O2 -Wall -Wextra -Werror -I "$task_app" "$task_stage/tests/test_eth_codec.c" -o "$task_out/test-eth"
"$task_out/test-eth"
echo "NATIVE VALIDATION PASS: parser + 18 dispatcher/lifecycle runs + 3 codecs; no MMIO"

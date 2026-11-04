#!/usr/bin/env bash
# Recompile only harness/production guard; explicitly reuse reviewed P3j core.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly output=${POWERLINK_BUILD_ROOT:?Existing P3j software-repro core}
readonly capture=${POWERLINK_CAPTURE_ROOT:?New capture directory}
test ! -e "$capture"
mkdir "$capture"
readonly port="$stage/source/powerlink/port"
readonly upstream="$output/source/openPOWERLINK_V2-2.7.2"
gcc -std=c11 -O2 -g -rdynamic -Wall -Wextra -Werror -UNDEBUG -DOPLK_TARGET_UNIPROTON -DCONFIG_MN \
    -include common/oplkinc.h -DM7_EDRV_NATIVE_TEST -I "$port" -I "$upstream/stack/include" -I "$upstream/contrib" \
    "$stage/tests/test_powerlink_cycle_p3j_capture.c" "$port/m7_cycle_probe.c" -Wl,--start-group \
    "$output/native/libm7_powerlink_passive_mn.a" "$output/native/core/libm7_powerlink_mn_core.a" \
    -Wl,--end-group -no-pie -Wl,--wrap=malloc,--wrap=calloc,--wrap=free,--wrap=oplk_execNmtCommand \
    -Wl,--wrap=m7_plk_fault,--wrap=edrv_freeTxBuffer,--wrap=m7_mn_process,--wrap=m7_eth2_hw_read \
    -Wl,--wrap=m7_eth2_hw_acquire,--wrap=edrvcyclic_stopCycle -o "$capture/probe"
for scenario in normal heap_full; do
    M7_P3J_NATIVE_CAPTURE="$capture/$scenario.bin" timeout 20s "$capture/probe" "$scenario"
    python3 "$stage/tests/verify_powerlink_cycle_p3j_capture.py" "$capture/$scenario.bin"
done

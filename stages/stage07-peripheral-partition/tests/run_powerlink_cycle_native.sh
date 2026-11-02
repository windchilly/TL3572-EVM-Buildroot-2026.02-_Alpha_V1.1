#!/usr/bin/env bash
# P3i REAL cyclic path; native hooks only, never board/SSH/deployment.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly port="$stage/source/powerlink/port"
readonly output=${POWERLINK_BUILD_ROOT:?Set full patched P3h software root}
readonly upstream="$output/source/openPOWERLINK_V2-2.7.2"
readonly work=$(mktemp -d /tmp/tl3572-plk-cycle.XXXXXX)
gcc -std=c11 -O2 -g -rdynamic -Wall -Wextra -Werror -UNDEBUG -DOPLK_TARGET_UNIPROTON -DCONFIG_MN \
    -include common/oplkinc.h -DM7_EDRV_NATIVE_TEST -I "$port" -I "$upstream/stack/include" -I "$upstream/contrib" \
    "$stage/tests/test_powerlink_cycle.c" -Wl,--start-group "$output/native/libm7_powerlink_passive_mn.a" \
    "$output/native/core/libm7_powerlink_mn_core.a" -Wl,--end-group -no-pie \
    -Wl,--wrap=malloc,--wrap=calloc,--wrap=free,--wrap=oplk_execNmtCommand,--wrap=m7_plk_fault,--wrap=edrv_freeTxBuffer -o "$work/cycle"
for scenario in normal heap_full wrong_owner dma_fault tx_error no_completion direct_off stop_failure timer_release_failure; do
    timeout 20s "$work/cycle" "$scenario"
done
for value in 0 1; do
    if gcc -std=c11 -DOPLK_TARGET_UNIPROTON -DCONFIG_MN -DTIMER_USE_EXT_SYNC_INT="$value" \
        -I "$port" -I "$upstream/stack/include" -I "$upstream/contrib" \
        -c "$port/hrestimer-rk3572.c" -o "$work/unsupported.o" > "$work/unsupported.log" 2>&1; then
        echo 'ERROR: unsupported external sync hardware compiled successfully' >&2; exit 1
    fi
    python3 -c 'import pathlib,sys;assert "RK3572 port has no external synchronization interrupt hardware" in pathlib.Path(sys.argv[1]).read_text();print("P3i explicit external-sync build rejected")' "$work/unsupported.log"
done

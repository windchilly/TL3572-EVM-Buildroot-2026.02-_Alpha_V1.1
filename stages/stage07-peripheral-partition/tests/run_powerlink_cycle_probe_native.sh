#!/usr/bin/env bash
# P3j real production guard+full stack; no board connection/permission.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly port="$stage/source/powerlink/port"
readonly output=${POWERLINK_BUILD_ROOT:?Set fresh full software root}
readonly upstream="$output/source/openPOWERLINK_V2-2.7.2"
readonly work=$(mktemp -d /tmp/tl3572-plk-cycle-guard.XXXXXX)
gcc -std=c11 -O2 -g -rdynamic -Wall -Wextra -Werror -UNDEBUG -DOPLK_TARGET_UNIPROTON -DCONFIG_MN \
    -include common/oplkinc.h -DM7_EDRV_NATIVE_TEST -I "$port" -I "$upstream/stack/include" -I "$upstream/contrib" \
    "$stage/tests/test_powerlink_cycle_probe.c" "$port/m7_cycle_probe.c" -Wl,--start-group \
    "$output/native/libm7_powerlink_passive_mn.a" "$output/native/core/libm7_powerlink_mn_core.a" \
    -Wl,--end-group -no-pie -Wl,--wrap=malloc,--wrap=calloc,--wrap=free,--wrap=oplk_execNmtCommand \
    -Wl,--wrap=m7_plk_fault,--wrap=edrv_freeTxBuffer,--wrap=m7_mn_process,--wrap=m7_eth2_hw_read \
    -Wl,--wrap=m7_eth2_hw_acquire,--wrap=edrvcyclic_stopCycle -o "$work/probe"
for scenario in normal heap_full heap_small context no_completion no_progress late dma_fault tx_error wrong_context nmt_timeout \
    reset_command off_command stop_cycle_failure stop_failure timer_release_failure readback total_budget; do
    timeout 20s "$work/probe" "$scenario"
done
readonly app="$stage/source/overlay/uniproton/demos/rk3572_mica/apps/openamp"
gates=(-DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_MN=1 -DM7_POWERLINK_TIMER_PROBE=1 -DM7_POWERLINK_ETH_PROBE=1
    -DM7_POWERLINK_EDRV_PROBE=1 -DM7_POWERLINK_MN_PROBE=1 -DM7_POWERLINK_NMT_PROBE=1 -DM7_POWERLINK_CYCLE_PROBE=1)
gcc -std=c11 -O2 -Wall -Wextra -Werror "${gates[@]}" -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" \
    -c "$app/rk3572_powerlink_app.c" -o "$work/owner.o"
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_MN=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" -c "$app/rk3572_integrated.c" -o "$work/integrated.o"
gcc -std=c11 -O2 -Wall -Wextra -Werror -UNDEBUG -DOPLK_TARGET_UNIPROTON -DCONFIG_MN \
    -include common/oplkinc.h -DM7_EDRV_NATIVE_TEST "${gates[@]}" -I "$port" -I "$upstream/stack/include" \
    -I "$upstream/contrib" -I "$app" -I "$stage/tests/integrated-stubs" \
    "$stage/tests/test_powerlink_cycle_probe_owner.c" "$work/owner.o" "$work/integrated.o" -Wl,--start-group \
    "$output/native/libm7_powerlink_passive_mn.a" "$output/native/core/libm7_powerlink_mn_core.a" \
    -Wl,--end-group -no-pie -Wl,--wrap=malloc,--wrap=calloc,--wrap=free -o "$work/owner"
for scenario in normal unsafe invalid reentrant; do timeout 20s "$work/owner" "$scenario"; done

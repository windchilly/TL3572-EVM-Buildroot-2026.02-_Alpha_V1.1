#!/usr/bin/env bash
# P3g native REAL stack; no board access, only hardware/time hooks mocked.
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly port="$stage/source/powerlink/port"
readonly app="$stage/source/overlay/uniproton/demos/rk3572_mica/apps/openamp"
readonly output=${POWERLINK_BUILD_ROOT:?Set full P3a software build root}
readonly upstream="$output/source/openPOWERLINK_V2-2.7.2"
readonly work=$(mktemp -d /tmp/tl3572-plk-nmt-probe.XXXXXX)
flags=(-std=c11 -O2 -Wall -Wextra -Werror -UNDEBUG -DOPLK_TARGET_UNIPROTON -DCONFIG_MN
    -include common/oplkinc.h -DM7_EDRV_NATIVE_TEST -I "$port" -I "$upstream/stack/include" -I "$upstream/contrib")
libs=(-Wl,--start-group "$output/native/libm7_powerlink_passive_mn.a" "$output/native/core/libm7_powerlink_mn_core.a"
    -Wl,--end-group -no-pie -Wl,--wrap=malloc,--wrap=calloc,--wrap=free,--wrap=oplk_execNmtCommand,--wrap=m7_mn_process,--wrap=nmtu_processEvent)
gcc "${flags[@]}" "$stage/tests/test_powerlink_nmt_probe.c" "$port/m7_nmt_probe.c" "$port/m7_mn_probe.c" "${libs[@]}" -o "$work/probe"
for scenario in normal context reset_command off_command reset_timeout off_timeout process phy stop timer_stop sleep dma mode readback tx wall_timeout; do
    timeout 15s "$work/probe" "$scenario"
done
for position in {17..25}; do timeout 15s "$work/probe" "allocation_$position"; done
gates=(-DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_TIMER_PROBE=1 -DM7_POWERLINK_ETH_PROBE=1
    -DM7_POWERLINK_EDRV_PROBE=1 -DM7_POWERLINK_MN_PROBE=1 -DM7_POWERLINK_NMT_PROBE=1)
gcc -std=c11 -O2 -Wall -Wextra -Werror "${gates[@]}" -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" \
    -c "$app/rk3572_powerlink_app.c" -o "$work/owner.o"
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_MN=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" -c "$app/rk3572_integrated.c" -o "$work/integrated.o"
ownerlibs=(-Wl,--start-group "$output/native/libm7_powerlink_passive_mn.a" "$output/native/core/libm7_powerlink_mn_core.a"
    -Wl,--end-group -no-pie -Wl,--wrap=malloc,--wrap=calloc,--wrap=free)
gcc "${flags[@]}" "${gates[@]}" -I "$app" -I "$stage/tests/integrated-stubs" "$stage/tests/test_powerlink_nmt_probe_owner.c" \
    "$work/owner.o" "$work/integrated.o" "${ownerlibs[@]}" -o "$work/owner"
for scenario in normal unsafe reentrant invalid; do timeout 15s "$work/owner" "$scenario"; done
bash "$stage/tests/run_powerlink_mn_probe_native.sh"
echo 'P3g bounded real NMT 25 + mailbox 4 scenarios PASS; prior cumulative regressions PASS; NO BOARD'

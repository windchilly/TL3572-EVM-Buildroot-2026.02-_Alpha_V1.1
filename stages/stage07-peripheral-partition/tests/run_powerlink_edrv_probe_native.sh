#!/usr/bin/env bash
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly port="$stage/source/powerlink/port"
readonly app="$stage/source/overlay/uniproton/demos/rk3572_mica/apps/openamp"
readonly output=${POWERLINK_BUILD_ROOT:?Set full P3a software build root}
readonly upstream="$output/source/openPOWERLINK_V2-2.7.2"
readonly work=$(mktemp -d /tmp/tl3572-plk-edrv-probe.XXXXXX)
flags=(-std=c11 -O2 -Wall -Wextra -Werror -UNDEBUG -DOPLK_TARGET_UNIPROTON -DCONFIG_MN
    -include common/oplkinc.h -I "$port" -I "$app" -I "$upstream/stack/include" -I "$upstream/contrib")
gcc "${flags[@]}" -DM7_EDRV_NATIVE_TEST "$stage/tests/test_powerlink_edrv_probe.c" \
    "$port/m7_edrv_probe.c" "$port/edrv-rk3572.c" "$port/target-uniproton.c" -no-pie -o "$work/probe"
python3 "$stage/tests/check_powerlink_edrv_codec.py" "$work/probe"
for scenario in normal no_peer frozen fcs body nonce duplicate truncated tx_error dma_fatal mode acquire start unsafe_acquire unsafe_start unsafe_stop context; do
    "$work/probe" "$scenario"
done
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 \
    -DM7_POWERLINK_TIMER_PROBE=1 -DM7_POWERLINK_ETH_PROBE=1 -DM7_POWERLINK_EDRV_PROBE=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" -c "$app/rk3572_powerlink_app.c" -o "$work/owner.o"
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_MN=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" -c "$app/rk3572_integrated.c" -o "$work/integrated.o"
gcc "${flags[@]}" -DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_TIMER_PROBE=1 -DM7_POWERLINK_ETH_PROBE=1 -DM7_POWERLINK_EDRV_PROBE=1 \
    -I "$stage/tests/integrated-stubs" "$stage/tests/test_powerlink_edrv_probe_owner.c" \
    "$work/owner.o" "$work/integrated.o" -Wl,--start-group "$output/native/libm7_powerlink_passive_mn.a" \
    "$output/native/core/libm7_powerlink_mn_core.a" -Wl,--end-group -no-pie \
    -Wl,--wrap=malloc,--wrap=calloc,--wrap=free -o "$work/owner"
for scenario in normal unsafe invalid; do "$work/owner" "$scenario"; done
bash "$stage/tests/run_powerlink_eth_native.sh"
echo 'P3e real EDRV/probe/target 17 + mailbox 3 scenarios PASS; previous cumulative regressions PASS'

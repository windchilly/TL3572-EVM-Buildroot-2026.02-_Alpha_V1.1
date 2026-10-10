#!/usr/bin/env bash
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly port="$stage/source/powerlink/port"
readonly app="$stage/source/overlay/uniproton/demos/rk3572_mica/apps/openamp"
readonly output=${POWERLINK_BUILD_ROOT:?Set P3a software build root}
readonly upstream="$output/source/openPOWERLINK_V2-2.7.2"
readonly work=$(mktemp -d /tmp/tl3572-plk-eth.XXXXXX)
flags=(-std=c11 -O2 -Wall -Wextra -Werror -UNDEBUG -DOPLK_TARGET_UNIPROTON -DCONFIG_MN
    -include common/oplkinc.h -I "$port" -I "$upstream/stack/include" -I "$upstream/contrib")
gcc "${flags[@]}" "$stage/tests/test_powerlink_eth_probe.c" "$port/m7_eth_probe.c" -o "$work/probe"
for scenario in normal context busy acquire unsafe_acquire unsafe_stop mode readbacks; do "$work/probe" "$scenario"; done
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 \
    -DM7_POWERLINK_TIMER_PROBE=1 -DM7_POWERLINK_ETH_PROBE=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" -c "$app/rk3572_powerlink_app.c" -o "$work/owner.o"
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_MN=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" -c "$app/rk3572_integrated.c" -o "$work/integrated.o"
gcc "${flags[@]}" -DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_TIMER_PROBE=1 -DM7_POWERLINK_ETH_PROBE=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" "$stage/tests/test_powerlink_eth_owner.c" \
    "$work/owner.o" "$work/integrated.o" -Wl,--start-group "$output/native/libm7_powerlink_passive_mn.a" \
    "$output/native/core/libm7_powerlink_mn_core.a" -Wl,--end-group -no-pie \
    -Wl,--wrap=malloc,--wrap=calloc,--wrap=free -o "$work/owner"
for scenario in normal unsafe invalid; do "$work/owner" "$scenario"; done
bash "$stage/tests/run_powerlink_timer_native.sh"
echo 'P3d native 8 probe + 3 cumulative mailbox scenarios PASS; P3c/P3b regressions PASS'

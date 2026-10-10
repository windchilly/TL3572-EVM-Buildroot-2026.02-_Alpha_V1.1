#!/usr/bin/env bash
set -euo pipefail
readonly stage=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
readonly app="$stage/source/overlay/uniproton/demos/rk3572_mica/apps/openamp"
readonly port="$stage/source/powerlink/port"
readonly output=${POWERLINK_BUILD_ROOT:?Set P3a software build root}
readonly upstream="$output/source/openPOWERLINK_V2-2.7.2"
readonly work=$(mktemp -d /tmp/tl3572-plk-owner.XXXXXX)
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" \
    -c "$app/rk3572_powerlink_app.c" -o "$work/owner.o"
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 -DM7_POWERLINK_MN=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" \
    -c "$app/rk3572_integrated.c" -o "$work/integrated.o"
gcc -std=c11 -O2 -UNDEBUG -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=5 -DOPLK_TARGET_UNIPROTON -DCONFIG_MN -DNDEBUG \
    -UNDEBUG -include common/oplkinc.h -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" \
    -I "$upstream/stack/include" -I "$upstream/contrib" \
    "$stage/tests/test_powerlink_owner.c" "$work/owner.o" "$work/integrated.o" \
    -Wl,--start-group "$output/native/libm7_powerlink_passive_mn.a" "$output/native/core/libm7_powerlink_mn_core.a" \
    -Wl,--end-group -no-pie -Wl,--wrap=malloc,--wrap=calloc,--wrap=free -o "$work/test-owner"
for scenario in dormant create_failure resume_failure delete_failure delay_failure delay_after_env owner_failure masked_failure stack_failure integrated integrated_create_failure integrated_resume_failure; do
    "$work/test-owner" "$scenario"
done
gcc -std=c11 -O2 -Wall -Wextra -Werror -DMCS_CLIENT_CPU_ID=4 -DM7_POWERLINK_MN=1 \
    -I "$stage/tests/integrated-stubs" -I "$app" -I "$port" \
    "$app/rk3572_integrated.c" "$stage/tests/test_integrated_dispatch.c" -o "$work/test-up1"
"$work/test-up1"
echo 'P3b REAL FULL-STACK OWNER NATIVE PASS: 12 scenarios + UP1 denial, 100 environment cycles, zero hardware acquire'

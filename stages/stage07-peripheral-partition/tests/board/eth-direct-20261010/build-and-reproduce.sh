#!/usr/bin/env bash
set -euo pipefail
task_project=${PROJECT_ROOT:-/home/openeuler/build/tl3572-2oo3}
task_stage=${STAGE_ROOT:-/home/openeuler/build/m7-eth-direct-20261010/stage}
task_tag=${REPRO_TAG:-verified-20261010}
for task_suffix in "$task_tag" "repro-$task_tag"; do
    export UNIPROTON_ROOT="$task_project/src/UniProton-m7-eth-direct-$task_suffix"
    bash "$task_stage/build/prepare_m7_integrated.sh"
    bash "$task_stage/build/build_m7_integrated.sh"
done
bash "$task_stage/build/verify_m7_integrated_repro.sh" \
    "$task_project/src/UniProton-m7-eth-direct-$task_tag/demos/rk3572_mica/build" \
    "$task_project/src/UniProton-m7-eth-direct-repro-$task_tag/demos/rk3572_mica/build"
bash "$task_stage/tests/run_integrated_native.sh"
bash "$task_stage/build/build_m7_eth2_power_hold.sh"

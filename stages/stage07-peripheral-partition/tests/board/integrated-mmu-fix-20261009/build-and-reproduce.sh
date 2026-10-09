#!/usr/bin/env bash
set -euo pipefail
task_project=${PROJECT_ROOT:-/home/openeuler/build/tl3572-2oo3}
task_stage=${STAGE_ROOT:-$task_project/m7-mmu-fix-20261009/stage}
task_tag=${REPRO_TAG:-v2-20261009}
for task_suffix in "$task_tag" "repro-$task_tag"; do
    export UNIPROTON_ROOT="$task_project/src/UniProton-m7-integrated-mmu-fix-$task_suffix"
    bash "$task_stage/build/prepare_m7_integrated.sh"
    bash "$task_stage/build/build_m7_integrated.sh"
done
bash "$task_stage/build/verify_m7_integrated_repro.sh" \
    "$task_project/src/UniProton-m7-integrated-mmu-fix-$task_tag/demos/rk3572_mica/build" \
    "$task_project/src/UniProton-m7-integrated-mmu-fix-repro-$task_tag/demos/rk3572_mica/build"
bash "$task_stage/tests/run_integrated_native.sh"

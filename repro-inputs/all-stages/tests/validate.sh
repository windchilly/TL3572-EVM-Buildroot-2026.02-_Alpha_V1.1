#!/usr/bin/env bash
# Host-side validation in seven new network-isolated containers. No board I/O.
set -euo pipefail
readonly repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
readonly parent=${STAGE_VALIDATION_ROOT:?Set a new absolute directory outside the repository}
[[ "${parent}" = /* && "${parent}" != / && "${parent}" != "${repo}" && "${parent}" != "${repo}/"* ]]
test ! -e "${parent}"
mkdir -p "${parent}/logs"
validate_stage() {
    local stage=$1
    export REPRO_STAGE="${stage}"
    export REPRO_CONTAINER="tl3572-all-${stage}-20260928"
    export REPRO_WORKSPACE="${parent}/${stage}"
    export REPRO_JOBS=4
    bash "${repo}/repro-inputs/all-stages/scripts/run.sh" prepare > "${parent}/logs/${stage}-prepare.log" 2>&1
    if [[ "${stage}" != stage01 ]]; then
        bash "${repo}/repro-inputs/all-stages/scripts/run.sh" fetch > "${parent}/logs/${stage}-fetch.log" 2>&1
    fi
    if [[ "${stage}" = stage05 ]]; then
        docker exec -e REPRO_JOBS=16 "${REPRO_CONTAINER}" bash /repo/repro-inputs/all-stages/scripts/build_up.sh stage05 > "${parent}/logs/stage05-up.log" 2>&1
    fi
    printf '%s validation PASS\n' "${stage}"
}
# Two independent stages at a time; cap concurrent disk and BitBake load.
stages=("$@")
if [[ "${#stages[@]}" -eq 0 ]]; then
    stages=(stage05 stage02 stage03 stage04 stage01 stage06 stage07)
fi
for ((index=0; index<${#stages[@]}; index+=2)); do
    pids=()
    for stage in "${stages[@]:index:2}"; do
        validate_stage "${stage}" &
        pids+=("$!")
    done
    for pid in "${pids[@]}"; do wait "${pid}"; done
done

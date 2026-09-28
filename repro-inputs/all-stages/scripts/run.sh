#!/usr/bin/env bash
set -euo pipefail
readonly repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
readonly stage=${REPRO_STAGE:?Set REPRO_STAGE to stage01..stage07}
readonly container=${REPRO_CONTAINER:-tl3572-${stage}-repro}
export REPRO_CONTAINER="${container}"
case "${stage}" in stage0[1-7]) ;; *) echo 'Invalid REPRO_STAGE' >&2; exit 2 ;; esac
case "${1:-prepare}" in
    prepare)
        bash "${repo}/repro-inputs/rk3572/scripts/run.sh" prepare
        docker exec "${container}" bash -c 'source /opt/buildtools/nativesdk/environment-setup-x86_64-openeulersdk-linux; python3 /repo/repro-inputs/all-stages/scripts/restore_profile.py --stage "$1" --jobs "$2"' bash "${stage}" "${REPRO_JOBS:-8}"
        ;;
    fetch|image)
        [[ "${stage}" != stage01 ]]
        docker exec "${container}" bash /repo/repro-inputs/all-stages/scripts/build_yocto.sh "${stage}" "$1"
        ;;
    up)
        [[ "${stage}" = stage05 || "${stage}" = stage06 || "${stage}" = stage07 ]]
        docker exec "${container}" bash /repo/repro-inputs/all-stages/scripts/build_up.sh "${stage}"
        ;;
    *) echo 'Usage: run.sh prepare|fetch|image|up' >&2; exit 2 ;;
esac

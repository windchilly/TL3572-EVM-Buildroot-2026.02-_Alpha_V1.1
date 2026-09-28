#!/usr/bin/env bash
set -euo pipefail

readonly image='swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container@sha256:b17c6b61bd379c5cf9a933ce69d6b37ae053c6fc95736de1e3f2e5aaad230e5f'
readonly repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
readonly container=${REPRO_CONTAINER:-tl3572-repro}
[[ "${REPRO_WORKSPACE:?Set REPRO_WORKSPACE to a new absolute Linux directory outside the repository}" = /* ]]
readonly workspace=$(realpath -m "${REPRO_WORKSPACE}")
readonly mode=${1:-prepare}

case "${mode}" in
    prepare)
        test "$(uname -m)" = x86_64
        [[ "${workspace}" = /* && "${workspace}" != / && "${workspace}" != "${repo}" && "${workspace}" != "${repo}/"* ]]
        test ! -e "${workspace}"
        docker pull "${image}"
        mkdir "${workspace}"
        docker run --rm --network none --user root --entrypoint /bin/bash \
            --mount "type=bind,src=${workspace},dst=/home/openeuler/build" \
            "${image}" -lc 'chown 1000:1000 /home/openeuler/build'
        docker create --name "${container}" --network none --user openeuler \
            --entrypoint /bin/bash -e REPRO_JOBS="${REPRO_JOBS:-8}" \
            --mount "type=bind,src=${repo},dst=/repo,readonly" \
            --mount "type=bind,src=${workspace},dst=/home/openeuler/build" \
            "${image}" -lc 'exec sleep infinity'
        docker start "${container}"
        docker exec "${container}" bash /repo/repro-inputs/rk3572/scripts/prepare.sh
        ;;
    fetch|m6-image|m7-mcs)
        docker exec "${container}" bash /repo/repro-inputs/rk3572/scripts/build_yocto.sh "${mode}"
        ;;
    m6-up|m7-up)
        docker exec "${container}" bash /repo/repro-inputs/rk3572/scripts/build_uniproton.sh "${mode%-up}"
        ;;
    *) echo 'Usage: run.sh prepare|fetch|m6-up|m7-up|m6-image|m7-mcs' >&2; exit 2 ;;
esac

#!/usr/bin/env bash
# Host-side smoke check using retained, read-only source archives. No board use.
set -euo pipefail
readonly retained=${1:?Provide an absolute existing pre-reorganization repository}
readonly target=${2:?Provide a new absolute verification directory}
readonly container=${3:?Provide a new Docker container name}
readonly prepare=${4:?Provide the current prepare.sh absolute path}
readonly image='swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container@sha256:b17c6b61bd379c5cf9a933ce69d6b37ae053c6fc95736de1e3f2e5aaad230e5f'
[[ "${retained}" = /* && "${target}" = /* && "${prepare}" = /* ]]
[[ "${target}" != / && "${target}" != "${retained}" && "${target}" != "${retained}/"* ]]
test -d "${retained}/repro-inputs/all-stages"
test -f "${prepare}"
test ! -e "${target}"
if docker container inspect "${container}" >/dev/null 2>&1; then
    echo 'Container already exists; refusing to reuse it' >&2
    exit 1
fi
docker image inspect "${image}" >/dev/null
bash -n "${prepare}"
mkdir -p "${target}/fixture/software/toolchains" "${target}/maintenance" "${target}/work"
# Absolute symlinks resolve only inside the container's read-only retained mount.
ln -s /retained/repro-inputs "${target}/fixture/repro-inputs"
ln -s /retained/stages "${target}/fixture/stages"
ln "${retained}/4-软件资料/Linux/Tools/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu.tar.gz" \
    "${target}/fixture/software/toolchains/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu.tar.gz"
cp "${prepare}" "${target}/maintenance/prepare.sh"
docker run --rm --network none --user root --entrypoint /bin/bash \
    --mount "type=bind,src=${target}/work,dst=/home/openeuler/build" \
    "${image}" -lc 'chown 1000:1000 /home/openeuler/build'
docker create --name "${container}" --network none --user openeuler --entrypoint /bin/bash \
    --mount "type=bind,src=${target}/fixture,dst=/repo,readonly" \
    --mount "type=bind,src=${retained},dst=/retained,readonly" \
    --mount "type=bind,src=${target}/maintenance,dst=/maintenance,readonly" \
    --mount "type=bind,src=${target}/work,dst=/home/openeuler/build" \
    "${image}" -lc 'exec sleep infinity'
trap 'docker stop "${container}" >/dev/null' EXIT
docker start "${container}"
# There is deliberately no /repo/4-* tree: the legacy fallback cannot be used.
docker exec "${container}" bash -c 'test ! -e /repo/4-*'
docker exec "${container}" bash /maintenance/prepare.sh > "${target}/prepare.log" 2>&1
docker exec "${container}" bash -c 'source /opt/buildtools/nativesdk/environment-setup-x86_64-openeulersdk-linux; python3 /repo/repro-inputs/all-stages/scripts/restore_profile.py --stage stage02 --jobs 8' \
    > "${target}/restore.log" 2>&1
docker exec "${container}" bash /repo/repro-inputs/all-stages/scripts/build_yocto.sh stage02 fetch \
    > "${target}/fetch.log" 2>&1
docker exec "${container}" bash -c 'set -e; source /opt/buildtools/nativesdk/environment-setup-x86_64-openeulersdk-linux; python3 /repo/repro-inputs/all-stages/tests/test_archive_utils.py; python3 /repo/stages/stage07-peripheral-partition/tests/test_up_log_reader.py' \
    > "${target}/unit-tests.log" 2>&1
printf 'PASS: new toolchain path, cold Stage02 restoration/fetch and Linux unit tests\n' | tee "${target}/result.log"

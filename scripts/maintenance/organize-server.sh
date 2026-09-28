#!/usr/bin/env bash
# Run on the Euler Docker HOST. Default is a read-only plan.
set -euo pipefail
readonly root=/home/docker_space/docker/volumes/dev_openeuler_vol-openeuler-build/_data
readonly control="${root}/projects/tl3572"
readonly record="${control}/maintenance/20260928"
readonly repo="${root}/tl3572-github-repro-20260928/repo-v2"

# Explicit allowlists only. Never delete the volume root or shared source/cache.
rk3588=(
    build-rk3588-uniproton-20260820
    build-rk3588-uniproton-mica-20260820
    rk3588_worktrees
    rk3588_reports
    vendor_sdk/rk3588_linux6.1_rkr6_v1
    artifacts/uniproton-rk3588-mica-20260820
    artifacts/rk3588-openeuler-ok3588-toolchain-20260820
    build/build-rk3588-openeuler-ok3588-toolchain-20260820
    r1-media
)
temporary=(
    tl3572-all-stages-export-20260928
    tl3572-all-stages-snapshots-20260928
    tl3572-all-stages-snapshots-v2-20260928/work
    tl3572-all-stages-snapshots-v2-20260928/profiles
    rk3572-input-export-20260928
    rk3572-input-export-20260928-v4
    tl3572-github-repro-20260928/work
    tl3572-github-repro-20260928/work-v2
)
moves=(
    'tl3572-github-repro-20260928|reproduction/20260928/github'
    'tl3572-all-stages-validation-20260928|reproduction/20260928/stage02-and-initial-m5'
    'tl3572-all-stages-validation-rest-20260928|reproduction/20260928/stage01-03-04-06-07'
    'tl3572-all-stages-validation-m5-final-20260928|reproduction/20260928/stage05-final'
    'rk3572-input-export-20260928-v5|exports/20260928/rk3572-inputs'
    'tl3572-all-stages-history-v2-20260928|exports/20260928/historical'
    'tl3572-all-stages-snapshots-v2-20260928|exports/20260928/all-stages'
    'tl3572-all-stages-evidence-20260928|evidence/20260928'
    'all-stage-verified-input-cache|cache/20260928/verified-inputs'
)
containers=(
    tl3572-repro-20260928 tl3572-repro2-20260928 tl3572-repro3-20260928
    tl3572-repro4-20260928 tl3572-repro-fetch-20260928 tl3572-repro-clone2-20260928
    tl3572-all-stage01-20260928 tl3572-all-stage02-20260928 tl3572-all-stage03-20260928
    tl3572-all-stage04-20260928 tl3572-all-stage05-20260928 tl3572-all-stage06-20260928
    tl3572-all-stage07-20260928 tl3572-all-stage05-20260928-m5-final
)

checked_path() {
    local path="${root}/$1"
    [[ "$1" != /* && "$1" != *..* && "${path}" != "${root}" ]]
    [[ "$(realpath -e "${path}")" = "${path}" ]]
    printf '%s\n' "${path}"
}
if [[ "${1:-}" != --apply ]]; then
    printf 'DELETE user-approved RK3588: %s\n' "${rk3588[@]}"
    printf 'DELETE redundant generated data (keep logs/manifests): %s\n' "${temporary[@]}"
    printf 'MOVE with original-path symlink: %s\n' "${moves[@]}"
    printf 'STOP completed test containers: %s\n' "${containers[@]}"
    exit 0
fi
[[ "$(id -u)" = 0 && "$(realpath -e "${root}")" = "${root}" ]]
test ! -e "${record}"
for relative in "${rk3588[@]}" "${temporary[@]}"; do checked_path "${relative}" > /dev/null; done
for mapping in "${moves[@]}"; do
    checked_path "${mapping%%|*}" > /dev/null
    test ! -e "${control}/${mapping#*|}"
done
# Frozen sources must be complete before any generated duplicate is removed.
for inputs in repro-inputs/all-stages repro-inputs/all-stages/historical repro-inputs/rk3572 repro-inputs/stage01-05; do
    (cd "${repo}/${inputs}" && sha256sum -c SHA256SUMS)
done
for name in "${containers[@]}"; do
    if [[ "$(docker inspect --format '{{.State.Running}}' "${name}")" = true ]]; then
        processes=$(docker top "${name}" -eo pid,args)
        if [[ "$(printf '%s\n' "${processes}" | awk 'NR>1 {$1=""; sub(/^[[:space:]]+/, ""); print}')" != 'sleep infinity' ]]; then
            echo "Test container has active work; refusing: ${name}" >&2; exit 1
        fi
    fi
done
# Dependency check includes the retained TL3572/RPi4 configurations and scripts.
if docker exec dev_openeuler grep -RIlE 'vendor_sdk|rk3588_worktrees|build-rk3588|rk3588_reports|r1-media' \
    /home/openeuler/build/tl3572-2oo3/.oebuild \
    /home/openeuler/build/tl3572-2oo3/build/build-tl3572/conf \
    /home/openeuler/build/tl3572-2oo3/meta-tl3572-stage3 \
    /home/openeuler/build/build-rpi4-mica-uniproton /home/openeuler/build/edk2-rpi4-20260818 \
    --include='*.sh' --include='*.py' --include='*.conf' --include='*.yaml' \
    --include='*.cmake' --include=CMakeLists.txt --exclude-dir=.git --exclude-dir=tmp --exclude-dir=build; then
    echo 'Retained project references an RK3588 removal target; refusing' >&2; exit 1
else
    result=$?; [[ "${result}" = 1 ]]
fi

mkdir -p "${record}" "${control}/archive/failed-runs/20260928"
exec > >(tee "${record}/actions.log") 2>&1
df -B1 "${root}" > "${record}/filesystem-before.txt"
docker inspect --format '{{.Name}} {{.State.Status}} image={{.Config.Image}} mounts={{json .Mounts}}' \
    "${containers[@]}" > "${record}/test-containers-before.log"
for relative in "${rk3588[@]}" "${temporary[@]}"; do
    du -s -B1 "$(checked_path "${relative}")" >> "${record}/deleted-allocated-bytes.tsv"
done
# Preserve failed-run logs and source inventories, not their generated copies.
for relative in "${temporary[@]}"; do
    destination="${control}/archive/failed-runs/20260928/${relative}"
    mkdir -p "${destination}"
    while IFS= read -r -d '' file; do cp -p -- "${file}" "${destination}/"; done < <(
        find "${root}/${relative}" -maxdepth 1 -type f \( -name '*.log' -o -name '*INVENTORY.json' -o -name SHA256SUMS \) -print0
    )
    if [[ -d "${root}/${relative}/tl3572-2oo3/logs" ]]; then
        cp -a "${root}/${relative}/tl3572-2oo3/logs" "${destination}/project-logs"
    fi
done
docker stop "${containers[@]}"
docker rm tl3572-repro-20260928 tl3572-repro2-20260928 tl3572-repro-fetch-20260928 tl3572-repro-clone2-20260928

# Unregister only the three approved worktrees, preserving shared Git repositories.
docker exec dev_openeuler git -c safe.directory=/usr1/openeuler/src/UniProton \
    -C /usr1/openeuler/src/UniProton worktree remove --force /home/openeuler/build/build-rk3588-uniproton-20260820
docker exec dev_openeuler git -c safe.directory=/usr1/openeuler/src/UniProton \
    -C /usr1/openeuler/src/UniProton worktree remove --force /home/openeuler/build/build-rk3588-uniproton-mica-20260820
sdk=/home/openeuler/build/vendor_sdk/rk3588_linux6.1_rkr6_v1/rk3588_linux6.1_rkr6_v1
docker exec dev_openeuler git -c safe.directory="${sdk}" -C "${sdk}" \
    worktree remove --force /home/openeuler/build/rk3588_worktrees/ctb8815-r1
for relative in "${rk3588[@]}" "${temporary[@]}"; do
    if [[ -e "${root}/${relative}" ]]; then
        path=$(checked_path "${relative}")
        rm -rf --one-file-system -- "${path}"
    fi
    printf 'DELETED %s\n' "${relative}"
done
for mapping in "${moves[@]}"; do
    origin=$(checked_path "${mapping%%|*}")
    destination="${control}/${mapping#*|}"
    mkdir -p "$(dirname "${destination}")"
    mv -- "${origin}" "${destination}"
    ln -s -- "$(realpath --relative-to="$(dirname "${origin}")" "${destination}")" "${origin}"
    printf 'MOVED %s -> %s (old path kept as symlink)\n' "${origin}" "${destination}"
done
# Loose export/build helpers and logs are classified without breaking old paths.
mkdir -p "${control}/tools/20260928" "${control}/evidence/20260928/export-driver-logs"
for name in prepare.sh run.sh build_uniproton.sh build_yocto.sh restore_verified_input_cache.py m7.conf \
    export-rk3572-inputs-20260928.py export-rk3572-inputs-20260928-v2.py \
    export-rk3572-inputs-20260928-v3.py export-rk3572-inputs-20260928-v4.py export-rk3572-inputs-20260928-v5.py; do
    origin=$(checked_path "${name}"); destination="${control}/tools/20260928/${name}"
    mv -- "${origin}" "${destination}"
    ln -s -- "$(realpath --relative-to="$(dirname "${origin}")" "${destination}")" "${origin}"
done
for name in tl3572-all-stages-export-20260928.log tl3572-all-stages-history-v2-20260928.log \
    tl3572-all-stages-snapshots-20260928.log tl3572-all-stages-snapshots-v2-20260928.log \
    tl3572-all-stages-validation-20260928.log tl3572-all-stages-validation-rest-20260928.log \
    tl3572-all-stages-validation-m5-final-20260928.log; do
    origin=$(checked_path "${name}"); destination="${control}/evidence/20260928/export-driver-logs/${name}"
    mv -- "${origin}" "${destination}"
    ln -s -- "$(realpath --relative-to="$(dirname "${origin}")" "${destination}")" "${origin}"
done
ln -s ../../tl3572-2oo3 "${control}/current"
mkdir -p "${root}/projects/rpi4" "${root}/projects/shared"
ln -s ../../build-rpi4-mica-uniproton "${root}/projects/rpi4/current"
ln -s ../../edk2-rpi4-20260818 "${root}/projects/rpi4/uefi"
ln -s ../../artifacts/rpi4-mica-uniproton-20260814-110750 "${root}/projects/rpi4/release-20260814"
ln -s ../../artifacts/rpi4-mica-uniproton-20260818-current "${root}/projects/rpi4/release-20260818"
for name in src downloads sstate-cache toolchains host-tools build-mcs; do
    ln -s "../../${name}" "${root}/projects/shared/${name}"
done
# Newly created classification directories remain writable by the SDK user.
# Do not recursively change the ownership of preserved repositories or inputs.
for directory in projects projects/tl3572 projects/tl3572/reproduction projects/tl3572/reproduction/20260928 \
    projects/tl3572/exports projects/tl3572/exports/20260928 projects/tl3572/evidence projects/tl3572/evidence/20260928 \
    projects/tl3572/evidence/20260928/export-driver-logs projects/tl3572/cache projects/tl3572/cache/20260928 \
    projects/tl3572/tools projects/tl3572/tools/20260928 projects/tl3572/archive projects/tl3572/archive/failed-runs \
    projects/tl3572/archive/failed-runs/20260928 projects/tl3572/maintenance projects/tl3572/maintenance/20260928 \
    projects/rpi4 projects/shared; do
    chown 1000:1000 "${root}/${directory}"
done
df -B1 "${root}" > "${record}/filesystem-after.txt"
docker ps -a --format '{{.Names}} {{.Status}}' > "${record}/containers-after.log"
echo 'Server directory organization complete. Original TL3572/RPi4/shared paths retained.'

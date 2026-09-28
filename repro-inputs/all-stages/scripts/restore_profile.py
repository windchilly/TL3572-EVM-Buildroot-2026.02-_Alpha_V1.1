#!/usr/bin/env python3
"""Restore a stage in a newly prepared, isolated RK3572 container workspace."""
import argparse
import json
from pathlib import Path
import shutil
import tarfile
from archive_utils import digest


PROJECT = Path("/home/openeuler/build/tl3572-2oo3")


def extract(path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path) as source:
        source.extractall(destination, filter="data")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("/repo"))
    parser.add_argument("--stage", choices=[f"stage{i:02}" for i in range(1, 8)], required=True)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    source = args.repo / "repro-inputs/all-stages"
    records = json.loads((source / "STAGES.json").read_text())
    stage = next(record for record in records["profiles"] if record["stage"] == args.stage)
    # This tool is never a switch-stage-in-place tool. Original build trees,
    # previously configured profiles and any compiled outputs are rejected.
    if (PROJECT / "STAGE.json").exists() or (PROJECT / "build/build-tl3572/tmp").exists() or (PROJECT / "src/UniProton/output").exists():
        raise ValueError("Only a newly prepared, unbuilt workspace may be restored")
    if args.jobs < 1:
        raise ValueError("jobs must be positive")
    sums = {}
    for line in (source / "SHA256SUMS").read_text().splitlines():
        checksum, name = line.split(None, 1)
        sums[name.strip()] = checksum

    def verified(name):
        path = source / name
        if digest(path) != sums[name]:
            raise ValueError(f"Corrupt source archive: {name}")
        return path

    historical = source / "historical"
    historical_sum = (historical / "SHA256SUMS").read_text().splitlines()[0].split()[0]
    kernel510 = historical / "openeuler-kernel-5.10-complete.tar.gz"
    if digest(kernel510) != historical_sum:
        raise ValueError("Corrupt complete openEuler 5.10 source")
    extract(kernel510, PROJECT / "src")
    effective = PROJECT / "stage-sources"
    effective.mkdir()
    (PROJECT / "src/UniProton").rename(PROJECT / "src/UniProton-default-m6")
    uni = PROJECT / ("src/UniProton-m7" if args.stage == "stage07" else "src/UniProton")
    if args.stage in ("stage05", "stage06", "stage07"):
        extract(verified(stage["source_bundles"]["UniProton"]), uni)
    else:
        extract(args.repo / "repro-inputs/stage01-05/upstream/UniProton.tar.gz", uni)
    default_layer = PROJECT / "meta-tl3572-stage3"
    default_layer.rename(PROJECT / "meta-tl3572-stage3-m6-reference")
    if args.stage != "stage01":
        profile = PROJECT / "stage-profile"
        extract(verified(stage["profile_bundle"]), profile)
        layer_name = "meta-tl3572" if args.stage == "stage02" else "meta-tl3572-stage3"
        shutil.copytree(profile / layer_name, PROJECT / layer_name)
        for item in stage["shared_files"]:
            original = args.repo / item["source"]
            if digest(original) != item["sha256"]:
                raise ValueError(f"Corrupt shared input: {item['source']}")
            destination = PROJECT / item["destination"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
        build = PROJECT / ("build/build-rootfs" if args.stage == "stage02" else "build/build-tl3572")
        shutil.copytree(profile / "build-conf", build / "conf", dirs_exist_ok=True)
        local = build / "conf/local.conf"
        with local.open("a") as output:
            output.write(f'\n# Independent frozen stage source profile.\nOPENEULER_FETCH = "disable"\nBB_NO_NETWORK = "1"\nSOURCE_DATE_EPOCH = "1787652448"\nSSTATE_DIR = "{PROJECT}/sstate-profile"\nBB_NUMBER_THREADS = "{args.jobs}"\nPARALLEL_MAKE = "-j {args.jobs}"\n')
        extract(verified(stage["source_bundles"]["mcs"]), effective / "mcs")
        if "kernel" in stage["source_bundles"]:
            extract(verified(stage["source_bundles"]["kernel"]), effective / "kernel-6.12.69")
    else:
        vendor = args.repo / "repro-inputs/meta-tl3572-stage3/recipes-kernel/linux/files/linux-6.12.69-v1.0-gf1b67c2.tar.gz"
        extract(vendor, effective / "vendor-kernel-6.12.69")
    (PROJECT / "STAGE.json").write_text(json.dumps(stage, indent=2, ensure_ascii=False) + "\n")
    print(f"Restored {args.stage}: {stage['provenance']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Materialize and freeze every stage's source profile from archived evidence.

Stage03-05 layers are evidence-based reconstructions, not original full-layer
snapshots. Complete effective kernels, MCS and UniProton are also exported.
Run on Linux, with the pinned repository's LFS source files hydrated.
"""
import argparse
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rk3572/scripts"))
from export_inputs import files_under
from archive_utils import archive, digest


def extract(bundle, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle) as source:
        source.extractall(destination, filter="data")


def apply(root, patch):
    for extra in (("--check",), ()):
        subprocess.run(["git", "-C", str(root), "apply", *extra, str(patch)], check=True)


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f"Expected exactly one anchor: {before!r}")
    return text.replace(before, after, 1)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "linux":
        raise ValueError("Export on Linux to preserve executable modes and symlinks")
    repo = args.repo.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    work = args.output / "work"
    work.mkdir()
    stages = repo / "stages"
    shared = repo / "repro-inputs"
    current = shared / "meta-tl3572-stage3"
    upstream = shared / "stage01-05/upstream"
    profile_root = args.output / "profiles"
    profile_root.mkdir()
    inventory = {"format": 1, "scope": "Stage01-07 formal closeout / implemented M7 software",
                 "profiles": [], "bundles": []}
    bundles = inventory["bundles"]

    def pack(root, filename, prefix=""):
        record = archive(args.output / filename,
                         [(path, prefix + path.relative_to(root).as_posix()) for path in files_under(root)])
        bundles.append(record)
        return filename

    # The complete shared trees remain in their existing immutable archives.
    inventory["shared_inputs"] = [
        {"path": path.relative_to(repo).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(upstream.glob("*.tar.gz"))
        + [shared / "rk3572/openeuler-packages.tar.gz", shared / "rk3572/downloads.tar.gz",
           shared / "rk3572/yocto-meta-openeuler-git.tar.gz",
           current / "recipes-kernel/linux/files/linux-6.12.69-v1.0-gf1b67c2.tar.gz"]]

    historical_script = (stages / "stage04-mica-mcs/worklog-20260916/logs/server-layer-setup-stage4.sh").read_text()
    recipe4 = historical_script.split("<<'BBEOF'\n", 1)[1].split("\nBBEOF", 1)[0] + "\n"
    recipe4 = replace_once(recipe4, "file://mcs-km-Makefile;subdir=mcs-km", "file://Makefile;subdir=mcs-km")
    old_vermagic = '    vm=$(grep -ao '
    start = recipe4.index(old_vermagic)
    end = recipe4.index("\n    # Vendor blobs", start)
    recipe4 = recipe4[:start] + '    grep -aq "vermagic=${TL3572_KO_VERMAGIC}" ${WORKDIR}/mcs-km/mcs_km.ko || bbfatal "mcs_km vermagic does not match ${TL3572_KO_VERMAGIC}"\n' + recipe4[end:]
    overlay4 = historical_script.split("<<'DTSEOF'\n", 1)[1].split("\nDTSEOF", 1)[0] + "\n"
    image5_path = stages / "stage05-uniproton/yocto/tl3572-openeuler-mcs-image.bb"
    image5 = image5_path.read_text()
    # Undo only the single-instance additions preserved in the final M5 recipe.
    image3 = re.sub(r'^TL3572_UNIPROTON_SHA256 = .*\n', '', image5, flags=re.M)
    image3 = image3.replace("    linux-tl3572 \\\n", "")
    begin = image3.index("    install -d ${IMAGE_ROOTFS}/etc/systemd/system/micad.service.d")
    end = image3.index("    ln -snf /lib/systemd/system/serial-getty@.service", begin)
    image3 = image3[:begin] + image3[end:]
    begin = image3.index("    ln -snf /etc/systemd/system/mcs-km-load.service")
    end = image3.index("\n    # The vendor 6.12", begin)
    image3 = image3[:begin] + '    rm -f ${IMAGE_ROOTFS}/etc/systemd/system/multi-user.target.wants/micad.service\n' + image3[end:]
    image4 = replace_once(image3, "    mcsctl \\\n", "    mcsctl \\\n    linux-tl3572 \\\n")
    m5_boot = stages / "stage05-uniproton/firmware/boot-tl3572-m5-final.img"
    blob = m5_boot.read_bytes()
    start = blob.index(b"IKCFG_ST") + 8
    config5 = gzip.decompress(blob[start:blob.index(b"IKCFG_ED", start)])
    config4_path = stages / "stage04-mica-mcs/release-update-20260916/tl3572-6.12.69.config"
    if config5 != config4_path.read_bytes():
        raise ValueError("M5 embedded configuration does not match the archived M4 configuration")

    for number in range(1, 8):
        stage = f"stage{number:02}"
        root = profile_root / stage
        root.mkdir()
        record = {"stage": stage, "shared_files": [], "source_bundles": {},
                  "provenance": "original archived inputs" if number not in (3, 4, 5) else "reconstructed from preserved recipes, scripts, configurations and final-source overlays",
                  "historical_layer_byte_identity": number not in (3, 4, 5)}
        if number == 1:
            record["notes"] = "Baseline source/environment inventory; no historical Stage1 firmware target was built."
            inventory["profiles"].append(record)
            continue
        layer_name = "meta-tl3572" if number == 2 else "meta-tl3572-stage3"
        layer = root / layer_name
        original = shared / "stage01-05/stage02/meta-tl3572" if number == 2 else current
        for path in files_under(original):
            relative = path.relative_to(original)
            # Small profile files are frozen separately; identical large input
            # objects are stored once and copied by the restoration script.
            if path.name.endswith((".tar.gz", ".elf", ".img")):
                if number < 4 and "recipes-kernel" in relative.parts:
                    continue
                if number < 6 and path.name.endswith(".elf"):
                    continue
                record["shared_files"].append({"source": path.relative_to(repo).as_posix(),
                                                "destination": f"{layer_name}/{relative.as_posix()}",
                                                "sha256": digest(path)})
            else:
                if number < 4 and "recipes-kernel" in relative.parts:
                    continue
                if number < 5 and (path.name.startswith("tl3572-up") or path.name in ("mcs-km-load.service", "micad-mcs-km.conf")):
                    continue
                if number == 5 and path.name in ("tl3572-up-a.conf", "tl3572-up-b.conf"):
                    continue
                if number < 5 and (relative.parts[:2] == ("recipes-mcs", "mcs-linux") and path.name != "mcsctl.bbappend"):
                    continue
                destination = layer / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
        conf_source = shared / "stage01-05/stage02/build-conf" if number == 2 else shared / "build-conf"
        shutil.copytree(conf_source, root / "build-conf")
        if number in (3, 4, 5):
            image = layer / "recipes-core/images/tl3572-openeuler-mcs-image.bb"
            write(image, {3: image3, 4: image4, 5: image5}[number])
            if number >= 4:
                kernel_files = layer / "recipes-kernel/linux/files"
                # Remove later-stage-only patches from these reconstructed profiles.
                for name in ("0002-cpu-reserve-selected-cpus-for-mcs.patch", "0004-arm64-mcs-add-second-reserved-sgi.patch"):
                    (kernel_files / name).unlink()
                sgi = args.historical / "surviving-inputs/stage04-reserved-sgi.patch" if number == 4 else stages / "stage05-uniproton/source/patches/kernel/0001-arm64-smp-reserve-sgi-for-mcs-km.patch"
                shutil.copy2(sgi, kernel_files / "0001-arm64-smp-reserve-SGI-for-mcs-km.patch")
                shutil.copy2(config4_path, kernel_files / "defconfig")
                module = shared / "stage01-05/stage04/mcs-km-tl3572"
                for name in ("Makefile", "mcs_km.c"):
                    shutil.copy2(module / name, kernel_files / name)
                write(kernel_files / "tl3572-mcs-overlay.dts", overlay4 if number == 4 else (current / "recipes-kernel/linux/files/tl3572-mcs-overlay.dts").read_text())
                recipe = recipe4
                if number == 5:
                    recipe = recipe.replace("stage 4", "stage 5").replace("stage-4", "stage-5").replace("195535ebebee247d99cda7596dbb62094a7465a24a2774df975a58133edcd0fe", "9b74be5ea7a8f39846d788ccc8fb5472d15288eed7f9e8347846422710c426e0")
                write(layer / "recipes-kernel/linux/linux-tl3572_6.12.69.bb", recipe)
            if number == 5:
                append = layer / "recipes-mcs/mcs-linux/mcs-linux.bbappend"
                shutil.copy2(stages / "stage05-uniproton/yocto/mcs-linux.bbappend", append)
                (append.parent / "files/0002-baremetal-rproc-route-dual-sgi-events.patch").unlink()
                record["shared_files"].append({"source": "stages/stage05-uniproton/firmware/rk3572-uniproton-final.elf",
                                                "destination": f"{layer_name}/recipes-core/images/files/rk3572-uniproton.elf",
                                                "sha256": digest(stages / "stage05-uniproton/firmware/rk3572-uniproton-final.elf")})
                record["m5_kernel_config"] = {"source": m5_boot.relative_to(repo).as_posix(), "method": "embedded IKCONFIG gzip", "sha256": digest(config4_path), "policy": "maxcpus=7"}
        if number == 7:
            # Fold the implemented RPC append into this independent source
            # profile; the M6 layer in the repository remains unchanged.
            patch_name = "0003-rpc-shared-log-lifecycle.patch"
            shutil.copy2(stages / f"stage07-peripheral-partition/source/patches/mcs/{patch_name}", layer / f"recipes-mcs/mcs-linux/files/{patch_name}")
            append = layer / "recipes-mcs/mcs-linux/mcs-linux.bbappend"
            write(append, append.read_text() + f'\nSRC_URI += "file://{patch_name}"\n')
            record["notes"] = "Implemented observability/RPC sources only; peripheral direct drivers and handover are not yet implemented. Linux kernel is identical to Stage06; image remains the M6 reference image."

        mcs = work / f"mcs-{stage}"
        extract(upstream / "mcs.tar.gz", mcs)
        if number >= 5:
            patch_dir = current / "recipes-mcs/mcs-linux/files"
            apply(mcs, patch_dir / "0001-mcs-rpmsg-tty-full-payload.patch")
            if number >= 6:
                apply(mcs, patch_dir / "0002-baremetal-rproc-route-dual-sgi-events.patch")
            if number == 7:
                apply(mcs, stages / "stage07-peripheral-partition/source/patches/mcs/0003-rpc-shared-log-lifecycle.patch")
        record["source_bundles"]["mcs"] = pack(mcs, f"{stage}-mcs-complete.tar.gz")
        if number >= 5:
            uni = work / f"UniProton-{stage}"
            extract(upstream / "UniProton.tar.gz", uni)
            if number == 5:
                # Dependencies alone are shared with M6. All stage-specific
                # modified files come exclusively from the preserved M5 overlay.
                with tarfile.open(shared / "rk3572/uniproton-m6-complete-overlay.tar.gz") as overlay:
                    dependencies = [member for member in overlay if member.name.startswith(("platform/libboundscheck/", "src/net/lwip/")) or member.name in ("demos/rk3572_mica/component/libmetal-2022.10.0.tar.gz", "demos/rk3572_mica/component/openamp-2022.10.1.tar.gz")]
                    overlay.extractall(uni, members=dependencies, filter="data")
                extract(stages / "stage05-uniproton/source/overlay/uniproton-rk3572-m5-source-overlay.tar.gz", uni)
            else:
                extract(shared / "rk3572/uniproton-m6-complete-overlay.tar.gz", uni)
                if number == 7:
                    apply(uni, stages / "stage07-peripheral-partition/source/patches/uniproton/0001-dual-boot-log-and-uart0-isolation.patch")
                    shutil.copy2(stages / "stage07-peripheral-partition/source/overlay/uniproton/demos/rk3572_mica/bsp/print.c", uni / "demos/rk3572_mica/bsp/print.c")
            record["source_bundles"]["UniProton"] = pack(uni, f"{stage}-uniproton-complete.tar.gz")
        if 4 <= number <= 6:
            kernel_root = work / f"kernel-{stage}"
            extract(current / "recipes-kernel/linux/files/linux-6.12.69-v1.0-gf1b67c2.tar.gz", kernel_root)
            kernel = kernel_root / "linux-6.12.69-v1.0-gf1b67c2"
            source_files = layer / "recipes-kernel/linux/files"
            for name in ("0001-arm64-smp-reserve-SGI-for-mcs-km.patch", "0002-cpu-reserve-selected-cpus-for-mcs.patch", "0004-arm64-mcs-add-second-reserved-sgi.patch"):
                if (source_files / name).exists():
                    apply(kernel, source_files / name)
            shutil.copy2(source_files / "defconfig", kernel / ".config")
            shutil.copy2(source_files / "localversion", kernel / "localversion")
            record["source_bundles"]["kernel"] = pack(kernel, f"{stage}-kernel-6.12.69-complete.tar.gz")
        elif number == 7:
            record["source_bundles"]["kernel"] = "stage06-kernel-6.12.69-complete.tar.gz"
        else:
            record["kernel"] = "complete shared pristine vendor 6.12.69; Stage02 userspace uses qemu-aarch64 metadata, not a board-deployed generic kernel"
        write(root / "PROVENANCE.json", json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        record["profile_bundle"] = pack(root, f"{stage}-profile.tar.gz")
        inventory["profiles"].append(record)

    pack(profile_root, "stage02-07-profiles.tar.gz")
    manifest = args.output / "SOURCE-INVENTORY.json"
    write(manifest, json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
    stages_manifest = args.output / "STAGES.json"
    write(stages_manifest, json.dumps({"format": 1, "profiles": inventory["profiles"], "shared_inputs": inventory["shared_inputs"]}, ensure_ascii=False, indent=2) + "\n")
    write(args.output / "SHA256SUMS", "\n".join(f"{item['sha256']}  {item['archive']}" for item in bundles) + f"\n{digest(manifest)}  SOURCE-INVENTORY.json\n{digest(stages_manifest)}  STAGES.json\n")
    print(json.dumps({"profiles": len(inventory["profiles"]), "archives": [{key: bundle[key] for key in ("archive", "bytes", "sha256")} for bundle in bundles]}, indent=2), flush=True)


if __name__ == "__main__":
    main()

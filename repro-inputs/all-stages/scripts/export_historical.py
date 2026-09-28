#!/usr/bin/env python3
"""Archive surviving early source inputs without touching the original build."""
import argparse
import difflib
import json
from pathlib import Path
import subprocess
from archive_utils import archive, digest
from export_inputs import git


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    kernel = args.project / "src/kernel-5.10"
    tracked = subprocess.check_output(["git", "-C", str(kernel), "ls-files", "-z"])
    entries = [(kernel / name, "kernel-5.10/" + name)
               for name in tracked.decode().split("\0") if name]
    bundle = archive(args.output / "openeuler-kernel-5.10-complete.tar.gz", entries)
    historical = args.output / "surviving-inputs"
    historical.mkdir()
    patch = []
    for name in ("arch/arm64/kernel/smp.c", "arch/arm64/include/asm/smp.h"):
        original = args.project / "kernel-src-pristine" / name
        modified = args.project / "build-kernel" / name
        patch.extend(difflib.unified_diff(original.read_text().splitlines(keepends=True),
                                          modified.read_text().splitlines(keepends=True),
                                          fromfile="a/" + name, tofile="b/" + name))
    patch_path = historical / "stage04-reserved-sgi.patch"
    patch_path.write_text("".join(patch), encoding="utf-8")
    if not patch:
        raise ValueError("Surviving Stage4 kernel contains no SGI adaptation")
    audit = {"format": 1, "kernel_5_10_commit": git(kernel, "rev-parse", "HEAD"),
             "kernel_5_10_tracked_changes": git(kernel, "diff", "--name-only", "HEAD").splitlines(),
             "kernel_5_10": bundle,
             "stage04_patch": {"source": "surviving build-kernel smp.c/smp.h versus kernel-src-pristine",
                                "sha256": digest(patch_path)},
             "historical_layer_search": "No independent Stage03/04/05 Git repository or untouched layer snapshot survives; final work/temp has only the Stage06 kernel task."}
    audit_path = args.output / "HISTORICAL-INVENTORY.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums = [f"{digest(path)}  {path.relative_to(args.output).as_posix()}"
            for path in (args.output / bundle["archive"], patch_path, audit_path)]
    (args.output / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"kernel_commit": audit["kernel_5_10_commit"],
                      "files": len(entries), "archive_bytes": bundle["bytes"],
                      "sha256": bundle["sha256"]}), flush=True)


if __name__ == "__main__":
    main()

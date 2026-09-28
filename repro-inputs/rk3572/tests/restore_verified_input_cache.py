#!/usr/bin/env python3
"""Optional test acceleration: inject only inputs matching committed LFS hashes.

Not required by run.sh. Run before compilation if a local source-archive cache
is available; never mount the original build directory in the clean builder.
"""
import argparse
import fnmatch
import hashlib
from pathlib import Path
import shutil
import subprocess


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--cache", type=Path, action="append", required=True)
    parser.add_argument("--extra-input", action="append", default=[],
                        help="Additional repository-relative LFS input to verify/hydrate")
    args = parser.parse_args()
    tracked = subprocess.check_output(["git", "-C", str(args.repo), "ls-files", "-z"])
    candidates = {}
    for cache in args.cache:
        paths = [cache] if cache.is_file() else cache.rglob("*")
        for path in paths:
            if path.is_file() and ".git" not in path.parts:
                candidates.setdefault(path.name, []).append(path)
    restored = verified = 0
    missing = []
    for name in tracked.decode("utf-8").split("\0"):
        if not (name.startswith("repro-inputs/") or
                fnmatch.fnmatch(name, "4-*/Linux/Tools/arm-gnu-toolchain*.tar.gz") or
                name in args.extra_input or
                name.startswith("stages/stage07-peripheral-partition/")):
            continue
        blob = subprocess.check_output(["git", "-C", str(args.repo), "show", f"HEAD:{name}"])
        if not blob.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            continue
        lines = blob.decode("ascii").splitlines()
        expected = lines[1].removeprefix("oid sha256:")
        size = int(lines[2].removeprefix("size "))
        destination = args.repo / name
        if destination.stat().st_size == size and digest(destination) == expected:
            verified += 1
            continue
        for candidate in candidates.get(destination.name, []):
            if candidate.stat().st_size == size and digest(candidate) == expected:
                shutil.copyfile(candidate, destination)
                restored += 1
                break
        else:
            missing.append(name)
    print(f"verified={verified} restored={restored} missing={len(missing)}", flush=True)
    for name in missing:
        print(f"MISSING {name}", flush=True)
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

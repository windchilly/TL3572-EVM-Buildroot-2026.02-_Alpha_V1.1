#!/usr/bin/env python3
"""Verify and unpack the complete pinned upstream, then apply the target selector."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile


def validate_members(members, prefix, file_count):
    files = 0
    seen = set()
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or ".." in path.parts or "\\" in member.name
                or not path.parts or path.parts[0] != prefix):
            raise ValueError(f"Unsafe archive member: {member.name}")
        if not (member.isfile() or member.isdir()) or member.name in seen:
            raise ValueError(f"Unexpected archive type/duplicate: {member.name}")
        seen.add(member.name)
        files += int(member.isfile())
    if files != file_count:
        raise ValueError(f"Upstream file count {files} != {file_count}")


def prepare(destination, source_root=None):
    root = source_root or Path(__file__).resolve().parents[1] / "source/powerlink"
    lock = json.loads((root / "upstream.lock.json").read_text(encoding="utf-8"))
    archive = root / lock["archive"]
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != lock["archive_sha256"] or archive.stat().st_size != lock["archive_bytes"]:
        raise ValueError("Upstream archive differs from lock; fetch Git LFS, do not bypass verification")
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite: {destination}")
    with tarfile.open(archive, "r:gz") as upstream:
        members = upstream.getmembers()
        validate_members(members, lock["archive_prefix"], lock["files"])
        if upstream.pax_headers.get("comment") != lock["commit"]:
            raise ValueError("Git archive commit differs from lock")
        destination.mkdir(parents=True)
        # Only pinned regular files/directories, validated before any extraction.
        # No symlink, hardlink, device, traversal, or pre-existing destination.
        if hasattr(tarfile, "data_filter"):
            upstream.extractall(destination, members=members, filter="data")
        else:
            upstream.extractall(destination, members=members)
    tree = destination / lock["archive_prefix"]
    for name in ("0001-uniproton-target-selection.patch", "0002-uniproton-no-fp-range.patch"):
        patch = root / "port" / name
        # This upstream blob uses CRLF; our tracked patches use LF on Linux/Windows.
        subprocess.run(["git", "apply", "--ignore-space-change", "--check", str(patch)], cwd=tree, check=True)
        subprocess.run(["git", "apply", "--ignore-space-change", str(patch)], cwd=tree, check=True)
    print(f"POWERLINK PREPARED: {lock['commit']} / {lock['files']} files / {tree}")
    return tree


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.destination)

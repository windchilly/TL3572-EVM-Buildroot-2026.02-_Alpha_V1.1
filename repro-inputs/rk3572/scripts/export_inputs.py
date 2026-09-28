#!/usr/bin/env python3
"""Export the effective RK3572 inputs, not build outputs or private Git metadata.

Run on the original build host. This is an archival tool, not a build prerequisite.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


EXCLUDED = {
    "yocto-meta-openeuler": "already archived in stage01-05/upstream",
    "yocto-poky": "already archived in stage01-05/upstream",
    "yocto-meta-openembedded": "already archived in stage01-05/upstream",
    "mcs": "already archived in stage01-05/upstream",
    "UniProton": "baseline already archived; effective source overlay exported separately",
    "OpenAMP": "already archived in stage01-05/upstream",
    "libmetal": "already archived in stage01-05/upstream",
    "UniProton-m7": "derived from the M6 source and the checked-in M7 patch/overlay",
    "mcs-m7": "derived from the MCS baseline and the checked-in M6/M7 patches",
    "mcs-m7-reprocheck": "duplicate validation worktree",
    "kernel-5.10": "unused generic kernel; active TL3572 kernel is the complete vendor 6.12.69 archive",
}


def git(path, *arguments):
    result = subprocess.run(["git", "-C", str(path), *arguments],
                            capture_output=True, check=True)
    return result.stdout.decode("utf-8", errors="strict").strip()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def files_under(root):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_file() or path.is_symlink():
            yield path


def archive(output, entries):
    records = []
    with output.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6) as zipped:
            with tarfile.open(fileobj=zipped, mode="w|") as bundle:
                for path, name in sorted(entries, key=lambda item: item[1]):
                    info = bundle.gettarinfo(str(path), arcname=name)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    if path.is_symlink():
                        if Path(info.linkname).is_absolute() or ".." in Path(info.linkname).parts:
                            raise ValueError(f"Non-portable symlink: {name} -> {info.linkname}")
                        bundle.addfile(info)
                        records.append({"path": name, "link": info.linkname})
                        continue
                    with path.open("rb") as stream:
                        prefix = stream.read(128)
                        if prefix.startswith(b"version https://git-lfs.github.com/spec/v1"):
                            raise ValueError(f"Unresolved Git LFS pointer: {path}")
                        stream.seek(0)
                        bundle.addfile(info, stream)
                    records.append({"path": name, "bytes": info.size,
                                    "sha256": digest(path)})
    return {"archive": output.name, "bytes": output.stat().st_size,
            "sha256": digest(output), "files": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = args.project / "src"
    inventory = {"format": 1, "project": str(args.project),
                 "container_reference": "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container@sha256:b17c6b61bd379c5cf9a933ce69d6b37ae053c6fc95736de1e3f2e5aaad230e5f",
                 "source_date_epoch": int(git(source / "yocto-meta-openeuler", "log", "-1", "--format=%ct")),
                 "excluded_source_directories": EXCLUDED, "repositories": [], "bundles": []}
    packages = []
    for repo in sorted(source.iterdir()):
        if not repo.is_dir() or repo.name in EXCLUDED:
            continue
        if repo.is_symlink():
            raise ValueError(f"Source repository is a symlink: {repo}")
        entries = [(path, f"src/{repo.name}/{path.relative_to(repo).as_posix()}")
                   for path in files_under(repo) if path.name not in ("file.lock",)]
        record = {"name": repo.name, "files": len(entries),
                  "bytes": sum(path.stat().st_size for path, _ in entries)}
        if (repo / ".git").exists():
            record["commit"] = git(repo, "rev-parse", "HEAD")
            record["tracked_changes"] = git(repo, "diff", "--name-only", "HEAD").splitlines()
            record["sparse_checkout"] = (repo / ".git/info/sparse-checkout").exists()
        inventory["repositories"].append(record)
        packages.extend(entries)
    inventory["bundles"].append(archive(args.output / "openeuler-packages.tar.gz", packages))

    # Mirror tarballs contain upstream Git objects where required by ordinary
    # BitBake git fetches. Do not archive live cache configuration, locks or .done.
    downloads = [(path, f"downloads/{path.name}") for path in sorted(args.downloads.iterdir())
                 if path.is_file() and not path.is_symlink()
                 and not path.name.endswith((".done", ".lock"))
                 and (".tar." in path.name or path.suffix in (".tgz", ".zip"))]
    inventory["bundles"].append(archive(args.output / "downloads.tar.gz", downloads))

    uni = source / "UniProton"
    changed = git(uni, "diff", "--name-only", "HEAD").splitlines()
    overlay_paths = {uni / path for path in changed}
    for relative in ("build/uniproton_config/config_armv8_rk3572",
                     "platform/libboundscheck", "demos/rk3572_mica"):
        for path in files_under(uni / relative):
            name = path.relative_to(uni).as_posix()
            # Exclude generated demo libs, expanded dependencies and build trees.
            if name.startswith("demos/rk3572_mica/libs/"):
                continue
            if name.startswith("demos/rk3572_mica/build/") and path.parent != uni / "demos/rk3572_mica/build":
                continue
            if name.startswith("demos/rk3572_mica/build/") and path.suffix not in (".sh", ".ld"):
                continue
            if name.startswith("demos/rk3572_mica/component/") and path.parent != uni / "demos/rk3572_mica/component":
                continue
            if path.suffix in (".elf", ".o", ".a", ".lib", ".bin", ".pyc"):
                continue
            overlay_paths.add(path)
    for relative in ("cmake/tool_chain/rk3572_armv8.cmake", "cmake/tool_chain/rk3572_armv8_config.cmake.in"):
        overlay_paths.add(uni / relative)
    entries = [(path, path.relative_to(uni).as_posix()) for path in overlay_paths]
    inventory["bundles"].append(archive(args.output / "uniproton-m6-complete-overlay.tar.gz", entries))
    inventory["uniproton_overlay"] = {
        "baseline_commit": git(uni, "rev-parse", "HEAD"),
        "tracked_changes": changed,
        "libboundscheck_provenance": "effective source files copied into the working tree on 2026-09-17; original fetched commit not recorded; file hashes freeze the exact input",
        "purpose": "effective M6 inputs including libboundscheck, patched dependency tarballs/patches and custom BSP; no generated libraries or ELF outputs",
    }
    manifest = args.output / "SOURCE-INVENTORY.json"
    manifest.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sums = [f"{bundle['sha256']}  {bundle['archive']}" for bundle in inventory["bundles"]]
    sums.append(f"{digest(manifest)}  {manifest.name}")
    (args.output / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"repositories": len(inventory["repositories"]),
                      "archives": [{key: bundle[key] for key in ("archive", "bytes", "sha256")}
                                   for bundle in inventory["bundles"]]}, indent=2), flush=True)


if __name__ == "__main__":
    main()

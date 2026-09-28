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
import shutil


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
                    if info.isdir():
                        bundle.addfile(info)
                        records.append({"path": name, "directory": True})
                        continue
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
    parser.add_argument("--reuse-bundles", type=Path,
                        help="Reuse unchanged packaging/download bundles from a previous export")
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
    previous = None
    if args.reuse_bundles:
        previous = json.loads((args.reuse_bundles / "SOURCE-INVENTORY.json").read_text(encoding="utf-8"))
        if inventory["repositories"] != previous["repositories"]:
            raise ValueError("Packaging repositories changed; do a complete export instead")
        for bundle in previous["bundles"][:1]:
            original = args.reuse_bundles / bundle["archive"]
            if digest(original) != bundle["sha256"]:
                raise ValueError(f"Corrupt cached bundle: {original}")
            shutil.copyfile(original, args.output / original.name)
        inventory["bundles"] = previous["bundles"][:1]
    else:
        inventory["bundles"].append(archive(args.output / "openeuler-packages.tar.gz", packages))

    # Some ordinary Git fetches have only a bare cache, without a generated
    # mirror tarball (notably neard). Export those as standalone sanitized Git
    # mirrors too; cloning locally materializes alternates and all needed refs.
    extra_mirrors = args.output / "extra-downloads"
    extra_mirrors.mkdir()
    inventory["additional_git_mirrors"] = []
    for original in sorted((args.downloads / "git2").iterdir()):
        mirror_name = f"git2_{original.name}.tar.gz"
        if not original.is_dir() or (args.downloads / mirror_name).exists():
            continue
        cloned = args.output / "mirror-git" / original.name
        subprocess.run(["git", "clone", "--mirror", "--no-hardlinks", original.as_uri(), str(cloned)],
                       check=True, capture_output=True)
        subprocess.run(["git", "--git-dir", str(cloned), "config", "--remove-section", "remote.origin"], check=True)
        entries = [(path, path.relative_to(cloned).as_posix())
                   for path in sorted(cloned.rglob("*"))
                   if path.relative_to(cloned).parts[0] not in ("hooks", "logs")]
        mirror = archive(extra_mirrors / mirror_name, entries)
        inventory["additional_git_mirrors"].append({"name": original.name, "archive": mirror_name,
                                                    "bytes": mirror["bytes"], "sha256": mirror["sha256"],
                                                    "commit": git(cloned, "rev-parse", "HEAD")})
    # Do not archive live cache configuration, locks or .done.
    downloads = [(path, f"downloads/{path.name}") for path in sorted(args.downloads.iterdir())
                 if path.is_file() and not path.is_symlink()
                 and not path.name.endswith((".done", ".lock"))
                 and (".tar." in path.name or path.suffix in (".tgz", ".zip"))]
    downloads.extend((path, f"downloads/{path.name}") for path in sorted(extra_mirrors.iterdir()))
    inventory["bundles"].append(archive(args.output / "downloads.tar.gz", downloads))

    uni = source / "UniProton"
    changed = git(uni, "diff", "--name-only", "HEAD").splitlines()
    overlay_paths = {uni / path for path in changed}
    for relative in ("build/uniproton_config/config_armv8_rk3572",
                     "platform/libboundscheck", "demos/rk3572_mica",
                     "src/net/lwip", "src/fs/fat/ff15"):
        if not (uni / relative).is_dir():
            if relative == "src/fs/fat/ff15":
                # CONFIG_OS_OPTION_DRIVER is disabled in the active RK3572
                # configuration, so the original build never fetched FatFs.
                continue
            raise ValueError(f"Effective third-party source missing: {uni / relative}")
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
            if name.startswith("demos/rk3572_mica/") and path.suffix in (".elf", ".o", ".a", ".lib", ".bin", ".pyc"):
                continue
            overlay_paths.add(path)
    for relative in ("cmake/tool_chain/rk3572_armv8.cmake", "cmake/tool_chain/rk3572_armv8_config.cmake.in"):
        overlay_paths.add(uni / relative)
    entries = [(path, path.relative_to(uni).as_posix()) for path in overlay_paths]
    inventory["bundles"].append(archive(args.output / "uniproton-m6-complete-overlay.tar.gz", entries))
    # os-base and systemd inspect this repository through GitPython/git log.
    # Preserve the exact commit as a shallow repository; no historical objects,
    # credentials, original remotes or hooks are needed.
    metadata = args.output / "metadata-git"
    subprocess.run(["git", "clone", "--bare", "--depth", "1", "--no-tags",
                    (source / "yocto-meta-openeuler").as_uri(), str(metadata)],
                   check=True, capture_output=True)
    subprocess.run(["git", "--git-dir", str(metadata), "config", "--remove-section", "remote.origin"], check=True)
    subprocess.run(["git", "--git-dir", str(metadata), "config", "core.bare", "false"], check=True)
    metadata_entries = [(path, f".git/{path.relative_to(metadata).as_posix()}")
                        for path in files_under(metadata)
                        if path.relative_to(metadata).parts[0] not in ("hooks", "logs")]
    inventory["bundles"].append(archive(args.output / "yocto-meta-openeuler-git.tar.gz", metadata_entries))
    inventory["yocto_git_metadata"] = {"commit": git(source / "yocto-meta-openeuler", "rev-parse", "HEAD"),
                                       "shallow": True, "remotes": [], "hooks": False,
                                       "purpose": "exact os-base OEE_REVISION and systemd SOURCE_DATE_EPOCH; no synthetic commit"}
    inventory["uniproton_overlay"] = {
        "baseline_commit": git(uni, "rev-parse", "HEAD"),
        "tracked_changes": changed,
        "libboundscheck_provenance": "effective source files copied into the working tree on 2026-09-17; original fetched commit not recorded; file hashes freeze the exact input",
        "lwip_provenance": "complete effective patched lwIP 2.1.3 source tree from src/net/lwip; CMake skips FetchContent when restored; frozen by per-file hashes",
        "fatfs": "ff15 is not used by the active RK3572 configuration (CONFIG_OS_OPTION_DRIVER disabled); no original fetched tree exists",
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

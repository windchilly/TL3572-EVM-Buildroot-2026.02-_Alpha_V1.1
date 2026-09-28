"""Deterministic source archives retaining safe in-tree relative symlinks."""
import gzip
import hashlib
from pathlib import Path
import posixpath
import tarfile


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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
                        target = posixpath.normpath(posixpath.join(posixpath.dirname(name), info.linkname))
                        if info.linkname.startswith("/") or target == ".." or target.startswith("../"):
                            raise ValueError(f"Symlink escapes source archive: {name} -> {info.linkname}")
                        bundle.addfile(info)
                        records.append({"path": name, "link": info.linkname})
                    elif info.isdir():
                        bundle.addfile(info)
                        records.append({"path": name, "directory": True})
                    else:
                        with path.open("rb") as stream:
                            if stream.read(128).startswith(b"version https://git-lfs.github.com/spec/v1"):
                                raise ValueError(f"Unresolved LFS pointer: {path}")
                            stream.seek(0)
                            bundle.addfile(info, stream)
                        records.append({"path": name, "bytes": info.size, "sha256": digest(path)})
    return {"archive": output.name, "bytes": output.stat().st_size,
            "sha256": digest(output), "files": records}

#!/usr/bin/env python3
"""Generate exact scoped P3a source/build/evidence delivery checksums."""
import hashlib
from pathlib import Path
from make_powerlink_p2_manifest import inputs as p2_inputs, REPO, STAGE

EVIDENCE = STAGE / "tests/powerlink-mn-p3a-20261010"


def inputs():
    # Include prior phase evidence too: P3a builds/tests P0/P1/P2 unchanged.
    files = p2_inputs()
    for folder in ("powerlink-mn-p0-20261010", "powerlink-mn-p1-20261010"):
        files += [x for x in (STAGE / "tests" / folder).iterdir() if x.is_file()]
    files += [x for x in EVIDENCE.iterdir() if x.is_file() and x.name != "SHA256SUMS"]
    return sorted(set(files), key=lambda x: x.relative_to(REPO).as_posix())


if __name__ == "__main__":
    files = inputs()
    lines = [hashlib.sha256(x.read_bytes()).hexdigest() + "  " + x.relative_to(REPO).as_posix() for x in files]
    (EVIDENCE / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P3a manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes; unrelated files excluded")

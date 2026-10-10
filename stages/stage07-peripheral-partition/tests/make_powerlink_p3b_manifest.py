#!/usr/bin/env python3
"""Scoped P3b source/build/evidence checksums, excludes unrelated user work."""
import hashlib
from make_powerlink_p3a_manifest import inputs as p3a_inputs, REPO, STAGE
EVIDENCE = STAGE / "tests/powerlink-mn-p3b-20261010"


def inputs():
    files = p3a_inputs()
    files += [x for x in EVIDENCE.iterdir() if x.is_file() and x.name != "SHA256SUMS"]
    files += [x for x in (EVIDENCE / "candidates").glob("*.elf")]
    files += [STAGE / "tests/run_powerlink_owner_native.sh"]
    return sorted(set(files), key=lambda x: x.relative_to(REPO).as_posix())


if __name__ == "__main__":
    files = inputs()
    lines = [hashlib.sha256(x.read_bytes()).hexdigest() + "  " + x.relative_to(REPO).as_posix() for x in files]
    (EVIDENCE / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P3b manifest: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes")

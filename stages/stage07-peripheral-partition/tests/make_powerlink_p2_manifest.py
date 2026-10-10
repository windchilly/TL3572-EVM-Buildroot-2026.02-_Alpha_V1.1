#!/usr/bin/env python3
"""Generate the scoped P2 delivery/input+evidence checksum artifact."""
import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stages/stage07-peripheral-partition"
EVIDENCE = STAGE / "tests/powerlink-mn-p2-20261010"


def inputs():
    files = [REPO / x for x in (".gitattributes", "README.md", "memory.md")]
    files += [STAGE / x for x in ("README.md", "build/README.md", "docs/m7.0-powerlink-mn-roadmap.md")]
    for folder in ("source/powerlink", "source/overlay", "source/patches/uniproton", "tests/integrated-stubs"):
        files += [x for x in (STAGE / folder).rglob("*") if x.is_file() and "__pycache__" not in x.parts]
    files += list((STAGE / "build").glob("*powerlink*.sh"))
    files += list((STAGE / "build").glob("*integrated.sh"))
    files += [STAGE / "build/prepare_m7_uniproton.sh", STAGE / "tests/run_integrated_native.sh"]
    for pattern in ("*.py", "*.c"):
        files += list((STAGE / "tests").glob(pattern))
    files += list((STAGE / "tests/board").glob("*.py"))
    files += list((STAGE / "source/host").glob("*.py"))
    files += list((STAGE / "firmware").glob("tl3572-m7-integrated-up-*.elf"))
    files += [x for x in EVIDENCE.iterdir() if x.is_file() and x.name != "SHA256SUMS"]
    return sorted(set(files), key=lambda x: x.relative_to(REPO).as_posix())


if __name__ == "__main__":
    files = inputs()
    lines = [hashlib.sha256(x.read_bytes()).hexdigest() + "  " + x.relative_to(REPO).as_posix() for x in files]
    (EVIDENCE / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P2 manifest generated: {len(files)} files, {sum(x.stat().st_size for x in files)} bytes; unrelated user files excluded")

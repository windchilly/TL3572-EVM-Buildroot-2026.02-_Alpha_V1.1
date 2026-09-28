# GitHub upload scope

Target repository: `windchilly/TL3572-EVM-Buildroot-2026.02-_Alpha_V1.1`.

This repository is intended to contain the project documentation, board
reference materials, vendor source inputs needed by the TL3572 work, and the
Stage 01-07 implementation and validation records. Large binary files that
are included are stored through Git LFS.

## Included

- `docs/project/` migration plan and `docs/vendor-notes/` update/getting-started
  PDFs and software feature notes.
- Root README plus `docs/operations/` directory ownership/maintenance records
  and `scripts/maintenance/` exact-target, preview-by-default maintenance tools.
- `hardware/` TL3572 specifications, core/carrier board CAD, BOM, pin definitions,
  design guides and component datasheets; `docs/manuals/` developer/test manuals.
- `software/` demos, vendor Buildroot,
  Linux kernel, and U-Boot source archives, Arm GNU 14.3 toolchain archive,
  vendor boot/loader inputs, and their small metadata files.
- `docs/reference/rockchip/` technical PDFs, patches and SBOM/reference files.
- `stages/` Stage 01-07 source overlays, patches, recipes, configurations,
  build and test scripts, logs, manifests, checksums, and small firmware or
  boot artifacts retained as validation references.
- `repro-inputs/` complete Stage 06 Yocto layer and the corresponding
  BitBake/oebuild configuration copied from the build server.
- `repro-inputs/stage01-05/` seven pinned upstream source snapshots, the
  earlier Stage 02 `meta-tl3572` layer, historical build configuration and
  scripts, and remaining Stage 03-05 source/configuration inputs copied from
  the openEuler build container.
- `repro-inputs/rk3572/`: 150 additional openEuler package source trees,
  required upstream source-mirror archives, the complete effective M6
  UniProton source overlay (including libboundscheck and patched lwIP), the
  required sanitized shallow Git metadata for yocto-meta-openeuler, source inventory,
  checksums, and clean-container preparation/build scripts.
- `repro-inputs/all-stages/`: complete effective Stage04/05/06 kernel trees,
  complete Stage05/06/07 UniProton trees and Stage02-07 MCS trees, the complete
  pinned openEuler 5.10 kernel, independent per-stage layer/configuration
  profiles, provenance inventories, checksums, and frozen-source restoration
  and build scripts. Identical large vendor inputs are shared by hash, not
  omitted. Stage03-05 profiles are evidence-based reconstructions, not
  untouched original historical layer snapshots.

## Omitted from Git

- Generated rootfs, full `update.img`, and ISO images. Their descriptions,
  checksums, and validation records remain where available.
- The 6.1 GiB vendor `LinuxSDK-v1.0.tar.gz`, 1.5 GiB download cache,
  and 1.3 GiB generated sysroot. They are not inputs to the documented
  openEuler stage build paths; used vendor source/toolchain/assets are
  archived separately. This is not an upload of the entire unrelated SDK.
- Third-party Windows installers and one identical duplicate U-Boot archive.
- After-sales and product repair forms, vendor marketing/selection booklet,
  chat-group promotional material, and the unused VMware helper. These were
  removed from the current local tree via the Windows Recycle Bin; existing
  Git history is retained, not rewritten.

The `.gitignore` is the definitive path list for omissions. After the
2026-09-28 cleanup, the complete vendor SDK/dl/sysroot archives and nested
vendor Git metadata are preserved under ignored `.local-only/`; the Ubuntu
desktop ISO and VMware installer are in the Windows Recycle Bin. The verified
identical extra U-Boot archive and regenerable bytecode caches were deleted.
The follow-up structural reorganization removed all seven numbered vendor
top-level directories and physically classified useful files into `hardware/`,
`software/` and `docs/`. Windows board tools are preserved by function under
`.local-only/tools/windows/`. Exact mappings and deletions are recorded in
`docs/operations/local-reorganization-plan.json`; ignored rootfs/update firmware
is still preserved locally under `software/firmware/`. Relocated LFS files keep
their original content hashes; no source archive is regenerated.
Formal stage outputs remain at their original paths. Some Stage 02-04 SHA256SUMS lists include
omitted image outputs and therefore cannot be checked in full from a clone.

## Reproduction requirements (updated 2026-09-28)

The complete Stage 06 Yocto layer and its vendor assets are under
`repro-inputs/`. Pinned Stage 01 upstream source trees are also archived at
`repro-inputs/stage01-05/upstream/`, without Git metadata. To rebuild,
follow `repro-inputs/rk3572/README.md`: provision the digest-pinned container
(including GCC 12.3 and Native SDK), restore all archived inputs, and build
in a new isolated directory. The Arm GNU 14.3 archive is included; scripts
restore the original command aliases and empty nosys.specs compatibility
file. The user explicitly selected online retrieval of the pinned Docker
image, not an additional Git LFS upload of the container image. No
passwords, tokens, private SSH keys or crash dumps are included. The container no
longer has untouched full-layer snapshots for every historical Stage 03-05
state; reconstructed independent source profiles are now archived under
`repro-inputs/all-stages/`, with their evidence and limitations explicitly
recorded. The exact clean-room validation scope and results are recorded in
`repro-inputs/rk3572/tests/clean-rebuild.md`; source completeness is not a
claim of bit-identical historical image reconstruction or M7 acceptance.
All-stage validation is recorded separately in
`repro-inputs/all-stages/tests/verification.md`.
The all-stage reproduction entry is `repro-inputs/all-stages/README.md`,
pinned to commit `2e6074a506111b301ffc146650ef15966da47bf5` (original directory layout, complete source
archives, final build scripts and validation evidence). Seven-stage
restoration, six-stage offline fetch and a fresh byte-identical M5 ELF
rebuild passed; this is not a claim that every historical full image was
rebuilt. The new archives and inventories passed 24 independent GitHub
download hash checks. The source-completion round added about 1.06 GiB;
after removing irrelevant after-sales/promotional materials, current checked-out
tracked file content is about 4.14 GiB, excluding ignored local materials and
Git/LFS historical caches. Renames do not upload another copy of source archives.
The archived Stage 06 build and board tests are documented under
`stages/stage06-multi-uniproton/`.

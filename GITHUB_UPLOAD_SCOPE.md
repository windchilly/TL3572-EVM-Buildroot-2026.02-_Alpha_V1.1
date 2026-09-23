# GitHub upload scope

Target repository: `windchilly/TL3572-EVM-Buildroot-2026.02-_Alpha_V1.1`.

This repository is intended to contain the project documentation, board
reference materials, vendor source inputs needed by the TL3572 work, and the
Stage 01-06 implementation and validation records. Large binary files that
are included are stored through Git LFS.

## Included

- Root project migration plan, product update note, and getting-started PDF.
- `1-产品规格书/`, `2-技术服务/`, `3-用户手册/`, and `5-硬件资料/`.
- `4-软件资料/` demos, source code, feature documents, vendor Buildroot,
  Linux kernel, and U-Boot source archives, Arm GNU 14.3 toolchain archive,
  vendor boot/loader inputs, and their small metadata files.
- `6-开发参考资料/` and `7-关于Tronlong/`, including PDFs and SBOM/reference files.
- `stages/` Stage 01-06 source overlays, patches, recipes, configurations,
  build and test scripts, logs, manifests, checksums, and small firmware or
  boot artifacts retained as validation references.
- `repro-inputs/` complete Stage 06 Yocto layer and the corresponding
  BitBake/oebuild configuration copied from the build server.

## Omitted from Git

- Generated rootfs, full `update.img`, and ISO images. Their descriptions,
  checksums, and validation records remain where available.
- The 6.1 GiB vendor `LinuxSDK-v1.0.tar.gz`, 1.5 GiB download cache,
  and 1.3 GiB generated sysroot. They are not inputs to the documented
  openEuler Stage 06 build path.
- Third-party Windows installers and one identical duplicate U-Boot archive.

The `.gitignore` is the definitive path list for omissions. The original
files remain in the local workspace. Some Stage 02-04 SHA256SUMS lists include
omitted image outputs and therefore cannot be checked in full from a clone.

## Reproduction requirements

The complete Stage 06 Yocto layer and its vendor assets are now under
`repro-inputs/`. To rebuild, provision the pinned upstream repositories,
container image, external openEuler toolchain, and download access described
in `stages/stage01-baseline/`. Restore the absolute workspace layout recorded
in `repro-inputs/README.md`. A clean-room rebuild from this GitHub clone has
not yet been run; the archived Stage 06 build and board tests are documented
under `stages/stage06-multi-uniproton/`.

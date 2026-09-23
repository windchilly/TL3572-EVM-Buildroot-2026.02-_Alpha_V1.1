# 项目交接记录（2026-09-23）

## 用户目标

将当前 TL3572 项目上传到公开且原本为空的仓库：
`https://github.com/windchilly/TL3572-EVM-Buildroot-2026.02-_Alpha_V1.1.git`。
用户明确要求纳入 `4-软件资料/`、`6-开发参考资料/`、`7-关于Tronlong/`
中的可上传资料；保留能复建当前 openEuler/MICA/双 UniProton 项目的源码、
配方、配置和构建输入。大型已生成镜像、ISO、ext4 不必上传；不使用 GitHub Release。

## 当前已完成

- 工作区根目录已初始化 Git 仓库，分支 `main`，远端 `origin` 指向上述 URL。
- 已完成本地提交 `c03df1d`：`Import TL3572 project sources, references and Stage 06 build inputs`。
- **尚未推送 GitHub**。最后检查时远端仍为空，本地 `git status` 干净。
- 本机 Git Credential Manager 已通过浏览器为 `windchilly` 完成登录，凭据可用；
  仓库本地提交身份为 `windchilly <windchilly@users.noreply.github.com>`。
- 本次提交共 1020 个文件，原始文件总量约 2.63 GiB；546 个文件经 Git LFS
  跟踪。`git lfs fsck` 已通过。
- Stage 06 的 `SHA256SUMS` 共 38 项，逐项校验通过。

## 已纳入的内容

- 根目录路线图、产品更新说明、开箱文档，`1-产品规格书/`、`2-技术服务/`、
  `3-用户手册/`、`5-硬件资料/`。
- `4-软件资料/` 中的 Demo、功能说明、Buildroot/内核/U-Boot 源码包、
  Arm GNU 14.3 工具链、厂商 boot 与 loader 等复建相关文件。
- `6-开发参考资料/` 的 Rockchip 文档、补丁、SBOM，以及 `7-关于Tronlong/`。
- `stages/` 的 Stage 01–06 文档、源码覆盖包、补丁、Yocto 配方、配置、
  测试脚本与日志、校验清单及小型固件/boot 验证产物。
- 已从构建机复制完整的最终 `meta-tl3572-stage3` Yocto 层（约 312 MiB）及
  BitBake、`.oebuild` 配置到 `repro-inputs/`。复建步骤与外部依赖见
  `repro-inputs/README.md`，上传范围说明见 `GITHUB_UPLOAD_SCOPE.md`。

## 已排除的内容

`.gitignore` 是权威清单。共排除 38 个原始文件：已生成的 rootfs/update 镜像、
ISO、6.1 GiB 原厂 LinuxSDK 压缩包、下载缓存、生成的 sysroot、第三方 Windows
安装工具和一个字节完全相同的 U-Boot 源码包副本。它们仍留在本地磁盘，未删除。
原始 Stage 02–04 的部分 SHA256SUMS 涉及被排除的镜像，因此克隆仓库后无法对
这些清单进行完整逐项验证；源代码和当前 Stage 06 层输入已保留。

## 复建与安全处理

- 远端构建机上的 Yocto 层已补齐；上游 Yocto/MCS/UniProton 仓库仍应按
  `stages/stage01-baseline/TL3572-stage01-baseline-manifest.md` 的提交拉取，
  容器镜像按其摘要固定。新的干净环境尚未执行全量复建。
- `repro-inputs/meta-tl3572-stage3/recipes-kernel/linux/files/` 的 BitBake
  重封装内核源码 SHA256 为
  `94ebe6676f276f731309234e23ca338cd529f2255fc09c6dddbf1e353d6a0985`；
  vendor boot SHA256 为
  `4f2bbfb25d0255a81ce8a7f18420a138c8225992574e06bf5d30176034fc4b92`。
- 仓库是公开的。原路线图和 Stage 04 交接文档中的构建机明文 SSH 密码已在
  **首次提交之前**删除；不要把任何密码、Token 或私钥写回仓库。本记录不保存凭据。
- `6-开发参考资料` 的中英文 Release 目录原本含嵌套 `.git`。其 Git 元数据已
  移到本地忽略目录 `.local-git-metadata-backup/`，六个实际发布文档已作为普通
  文件进入主仓库，避免出现无法克隆内容的 Git 指针。

## 下一步

1. 再次确认 `git status --short` 干净、`git remote -v` 指向目标仓库。
2. 执行 `git push -u origin main`。Git LFS 会随推送上传二进制对象；初次上传
   体积较大，应等待其完成，勿重复发起并行推送。
3. 推送后用 `git ls-remote origin refs/heads/main`、GitHub 网页目录及 LFS
   文件下载核对远端；如遇配额或权限错误，记录原始错误再处理。
4. 如需验证复建，按 `repro-inputs/README.md` 在指定容器和上游源码提交中运行；
   当前只有历史构建（2920/2920、零 warning）与板卡实测记录，未从 GitHub
   克隆后重新构建。

当前用户请求是写好本文件供其他模型交接，因此本轮停在本地提交，未继续推送。

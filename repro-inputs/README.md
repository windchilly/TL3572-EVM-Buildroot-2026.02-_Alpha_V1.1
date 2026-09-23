# Stage 06 复建输入

本目录从构建机 `/home/openeuler/build/tl3572-2oo3/` 复制了最终
`meta-tl3572-stage3/`、`build/build-tl3572/conf/` 和 `.oebuild/` 配置。
Yocto 层内含 Stage 06 当前配方、补丁、厂商资产覆盖包、内核源码包、
vendor boot、配置及 UniProton A/B 固件。该内核源码包是为 BitBake 重新封装的
版本，SHA256 为
`94ebe6676f276f731309234e23ca338cd529f2255fc09c6dddbf1e353d6a0985`；
原厂压缩包位于 `4-软件资料/Linux/Kernel/src/`，两者字节哈希不同。
Yocto 层内 `vendor-boot.img` SHA256 为
`4f2bbfb25d0255a81ce8a7f18420a138c8225992574e06bf5d30176034fc4b92`。

复建时将 `meta-tl3572-stage3/` 放到
`/home/openeuler/build/tl3572-2oo3/meta-tl3572-stage3/`，将 `build-conf/`
内文件放到 `build/build-tl3572/conf/`，将 `.oebuild/` 放到工作区根目录。
这些配置固定使用构建机上的绝对路径；改变工作区位置时需要同步修改配置和
`stages/stage06-multi-uniproton/build/rebuild-m6-dual-image.sh`。

Stage 01–05 在构建容器中保留的七个上游源码工作树、早期 `meta-tl3572` 层、
配置和脚本已另行归档到 `stage01-05/`，内容及历史快照限制见其 `README.md`。

其余前置输入：

1. 按 `stages/stage01-baseline/TL3572-stage01-baseline-manifest.md` 固定七个上游
   仓库提交和 openEuler 容器镜像摘要。七个提交的源码快照可从
   `stage01-05/upstream/` 解压；这些压缩包不含 Git 历史。
2. 从 `4-软件资料/Linux/Tools/` 提供 Arm GNU 14.3 工具链到
   `/home/openeuler/build/tl3572-2oo3/toolchain-14.3/`。openEuler GCC 12.3 和
   Native SDK 由记录中的容器环境提供。
3. 若要从源码重编 UniProton A/B，先对指定 UniProton 提交应用 Stage 05 的源码
   覆盖包，再覆盖 Stage 06 的 `source/overlay/uniproton/`，运行其中的
   `build_m6_instances.sh`，并把两个 ELF 放进本层的镜像配方文件目录。
4. 在容器中运行 `stages/stage06-multi-uniproton/build/rebuild-m6-dual-image.sh`。

历史实测构建为 2920/2920 任务成功、零 warning；当前归档尚未在另一台构建机上
重新执行一次干净复建。下载缓存和 sstate 不在仓库中，首次构建需要联网并会耗时。

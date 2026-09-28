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
- 已于 2026-09-23 将 `main` 首次推送到 GitHub，并设置本地分支跟踪
  `origin/main`；首次推送成功，无权限或配额错误。
- 本机 Git Credential Manager 已通过浏览器为 `windchilly` 完成登录，凭据可用；
  仓库本地提交身份为 `windchilly <windchilly@users.noreply.github.com>`。
- 首次导入共 1020 个文件，原始文件总量约 2.63 GiB；546 个文件经 Git LFS
  跟踪。`git lfs fsck` 已通过；首次推送实际上传 522 个去重后的 LFS 对象，
  共约 2.5 GB。
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
- 2026-09-23 再次进入 `dev_openeuler` 容器，归档 Stage 01 的七个固定提交源码
  快照，以及容器中仍保留的 Stage 02 `meta-tl3572` 层、Stage 02–04 构建配置与
  脚本、Stage 03 历史配方和 Stage 04/05 额外源码配置；见
  `repro-inputs/stage01-05/README.md` 与该目录的 `SHA256SUMS`。

## 已排除的内容

`.gitignore` 是权威清单。共排除 38 个原始文件：已生成的 rootfs/update 镜像、
ISO、6.1 GiB 原厂 LinuxSDK 压缩包、下载缓存、生成的 sysroot、第三方 Windows
安装工具和一个字节完全相同的 U-Boot 源码包副本。它们仍留在本地磁盘，未删除。
原始 Stage 02–04 的部分 SHA256SUMS 涉及被排除的镜像，因此克隆仓库后无法对
这些清单进行完整逐项验证；源代码和当前 Stage 06 层输入已保留。

## 复建与安全处理

- 远端构建机上的最终 Yocto 层已补齐；上游 Yocto/MCS/UniProton 等七个仓库的
  固定提交源码也已归档在 `repro-inputs/stage01-05/upstream/`，不含 Git 历史。
  容器镜像仍按 Stage 01 清单摘要固定。Stage 03–05 各自未经修改的完整历史层
  快照在容器中未找到；新的干净环境尚未执行全量复建。
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

## 推送后验证

- `git ls-remote origin refs/heads/main` 与本地 `HEAD` 一致。
- 已从 GitHub 做一次全新的 `main` 浅克隆，克隆提交与本地一致。
- 已在新克隆中单独下载 LFS 样本
  `1-产品规格书/配件规格书/RG200U 5G通信模块规格书 .pdf`；远端下载文件与
  本地文件的 SHA256 均为
  `47808e1f5f5471885f7bcb32b6faa5d6e9852c6f7124b3cc9ace49dd530f18cb`。
- GitHub 仓库网页可匿名访问并标记为 Public。验证用临时克隆已删除。

## 后续可选工作

如需验证复建，按 `repro-inputs/README.md` 在指定容器和上游源码提交中运行；
当前只有历史构建（2920/2920、零 warning）与板卡实测记录，尚未从 GitHub
全新克隆后执行完整构建。除此之外，本次公开仓库上传任务已完成。

## 2026-09-28：M7.0 实施中的新增交接

- 用户已批准 M7.0 功能划分：UP1=CPU4，负责 CAN FD1/2、UART1 RS-485 #1、UART4 RS-232 #1、整颗 SARADC；UP2=CPU5，负责 CAN FD3/4、UART2 RS-485 #2、UART8 RS-232 #2、候选 ETH2/GMAC1。openEuler 保留 ETH1/ETH3、I2C1/XL9555、DI/DO 与系统资源。UP2 可接受启动阶段一次性 PHY reset，但运行期必须独立控制 GMAC1/MDIO/PHY，不能通过 Linux 或 RPMsg 代驱。UART4/8 正式运行属于工控通信；日志改用独立内存环与 Linux 收集。本阶段不考虑 2oo3。完整边界见 `stages/stage07-peripheral-partition/docs/`。
- 板卡 IP 为 `192.168.2.141`。用户确认目前没有 CAN/串口/ADC/ETH2 隔离测试对端；先做软件准备，不得将外设实际收发列为 PASS，也不向真实执行器发控制帧。
- M7.0 仍未完成。`stages/stage07-peripheral-partition/` 已新增内存日志环、UART0 打印隔离、双 ELF 构建脚本、Linux `/dev/mem` 日志读取及 systemd 模板、实机基线 DTB/DTS、资源台账和首轮记录。双旧版测试 ELF 曾在板上同时启动，双路各 100 次 RPMsg 回显及各 2 次单边停启通过，内存日志各留三轮 9 条启动事件。最终 ELF 后来修正格式截断边界并重编，于 2026-09-28 分别完成单实例启动、9 条启动日志、100 次 451 B RPMsg 回显、持久收集、停止和移除复测；见 `tests/board/m7-final-elf-single-instance-20260928.md`。Python 读取器 5 项单测通过；日志服务安装但 inactive/disabled，M6 固件及配置未覆盖。
- 重要故障（首轮历史状态；后续修复见下一节）：测试结束按顺序停止两个临时 `up-a-m7/up-b-m7` 时，第二个停止导致 `micad` 收到 `SIGABRT`。systemd 自动重启；当时 `micad` active，原有 M6 `up-a/up-b` Offline，SSH/ETH1 可用。当时根因未查，未修复版本不应重复双实例最终收尾压力测试。详见 `stages/stage07-peripheral-partition/tests/board/m7-observability-bringup-20260928.md`。
- 该崩溃留下的 CPU5 残留状态在最终 ELF 首次单实例启动时表现为 PSCI `CPU_ON=-4`（ALREADY_ON），没有新 RPMsg/日志，但 `mcsctl status` 误报 `Running` 且失败命令退出码仍为 0。经用户允许重启板卡一次后，UP2 最终 ELF 单实例复测通过；温重启后的日志环保留旧记录。随后 UP2 单独停止/移除成功，板卡回到原 M6 两实例 Offline、`micad` active、ETH1 正常、无 failed units。双实例连续停止故障仍未解决。
- 生效 M6 DT 中 CAN0–3、UART1/2/4/8、SARADC、GMAC0/1 当前仍由 Linux 绑定，尚无 M7 外设移交或直驱驱动。ETH2 `eth1` 当前 NO-CARRIER；管理口 ETH1 是 Linux `eth0`。板卡生效 DT 已导出为 Stage07 测试材料，具体 MMIO/IRQ/共享依赖见 `m7.0-live-resource-ledger.md`。
- 本地 M7 变化尚未提交或推送 GitHub；不得称 M7.0 已发布。公开仓库继续禁止密码、Token、私钥。

## 2026-09-28：micad 双停止 RPC 日志故障已修复、最终版本回归通过

- 在原 `/usr/bin/micad` 上再次复现第二路停止 `SIGABRT`，GDB 控制线程堆栈为 `free/fclose → RPC terminate → mica_unregister_all_services → mica_stop`。原二进制反汇编与 MCS 源码对应：每路初始化覆盖全局 `FILE *fp`，各路停止又关闭同一指针而不清空。单边停止后立即重启会重新开句柄，故此前的单边启停 PASS 不覆盖此问题。
- 用户明确批准“修复并重启回归”。本轮仅重启板卡一次，恢复崩溃遗留的 CPU5；Boot ID 现在是 `808eec59-7c3b-46dc-9b3e-f6dc658c5290`。随后只重启守护进程用于部署/清理，没有再次重启板卡。
- 新增 `source/patches/mcs/0003-rpc-shared-log-lifecycle.patch`：共享日志引用计数、首次打开/最后关闭、关闭后清空句柄、初始化失败清理及服务注册失败回退。使用独立 MCS 源码副本并保留 M6 的全载荷/双 SGI 补丁，原上游源码与 M6 构建层未修改。
- 最终 daemon 是 `stages/stage07-peripheral-partition/firmware/micad-m7-rpc-fix`，SHA-256 `40b7791d55ea58edb92d0119bd985ad560b2d3e1a1eba26ed1aa6566f907d20c`，保留 PIE、RELRO/NOW、栈保护，带调试信息、无主机 RPATH。两份独立源码树逐文件一致、均编译成功；仍有上游 UMT 未使用变量 warning。构建脚本/回退说明在 `build/`，M7 附加 Yocto 层已验证解析出三份补丁，但尚未重打完整镜像/RPM。
- 最终 PIE 版本两种停止顺序各 20 轮，交替两种启动顺序，共 40 轮全部 PASS，197.683 s；期间 PID 2319 不变、`NRestarts=0`，每轮离线 fd=17，RPC 两份日志运行时各仅一份、最终都关闭；每次停止对应 CPU 确认 OFF，无 tty 残留。两个测试段分别双路各 1000 次 451 B 回显、各 10 次单边启停通过。GDB 再验引用数 `0→1→2→1→0`，句柄只在最后停止时关闭/清空。
- 最终版本与原 M6 两份 ELF 的兼容回归也通过：四个启动/停止顺序组合、双路回显与单边启停正常。原 M6 `/lib/firmware/` 两 ELF 及配置、内核、设备树未覆盖。两路内存日志收集在压力测试中实际写入 `/userdata/uniproton-logs`，结束后服务 inactive/disabled；读取器 5 项单测 PASS，三份交付文件 SHA256SUMS 全部通过。
- 板卡持久使用 `/usr/libexec/m7/micad`，由 `/etc/systemd/system/micad.service.d/90-m7-rpc-fix.conf` 修改 ExecStart；原 `/usr/bin/micad`（SHA-256 `d6722cc43f411c4fb3a00c257d82e3bef74819521f3587ae64e327e752aa6dae`）及 `10-mcs-km.conf` 保留，临时 `/run` drop-in 已移除。临时 M7 配置已删除，只留原 `up-a/up-b` Offline。最终清理后服务 PID 4028 active、无 failed units，CPU4/5 OFF、ETH1/SSH 正常。
- 独立遗留问题：`create/rm` 临时实例后残留两个 `/dev/mcs` fd；上游 baremetal `rproc_init` 每次打开并覆盖全局 `mcs_fd`，remove 只在没有 bare-metal 客户端时关闭当前 fd。此问题未纳入 RPC 补丁，不能声称整个 MCS 创建/删除路径无泄漏。最后在两 CPU OFF 后手动重启守护进程清理。另 `mcsctl` 失败仍可退出 0、状态可误报 Running 的问题未修；自动化应继续联合成功消息、实际 RPMsg/日志与 PSCI 状态判断。
- 完整记录：`stages/stage07-peripheral-partition/tests/board/m7-rpc-log-lifecycle-fix-20260928.md`，原始最终结果为 `rpc-fix-final-pie-regression.log`、`rpc-fix-final-pie-probe.log`、`rpc-fix-final-pie-m6-compatibility.log`。原版约 227 MB core 只在板卡，可能含私密进程数据，禁止上传；Stage07 `.gitignore` 排除了 core 和 Python 缓存。
- M7.0 仍未验收：工业外设未移交，未做物理 CAN/UART/ADC/ETH2 收发；当前完成的是日志与指定 RPC 清理故障修复。本轮所有材料仍未提交或推送 GitHub。

## 2026-09-28：RK3572 构建输入完整性补齐进行中

- 用户要求分析实际 RK3572 构建位置，并把换机复现过程/输入完整上传 GitHub；
  已确认采用固定 Docker 摘要联网下载，不额外上传约 11.16 GiB 展开的容器镜像。
- 实际项目位于 `10.100.60.226` 的 `dev_openeuler` 容器
  `/home/openeuler/build/tl3572-2oo3`；宿主机构建卷为
  `/home/docker_space/docker/volumes/dev_openeuler_vol-openeuler-build/_data`。
- 在基础镜像的新临时容器验证 Native SDK 和 GCC 12.3 已包含；不是依赖旧容器内安装。
- 现有七仓归档之外，补充另外 150 个包输入目录（约 468.81 MiB）、必需的上游
  下载源镜像（11.83 MiB）、UniProton 的完整有效源码覆盖（1.14 MiB，含原未归档
  libboundscheck、实际 OpenAMP/libmetal 补丁与源包）。三个归档总计 505,178,765 B。
- 新入口 `repro-inputs/rk3572/README.md`；脚本创建独立空工作区并断网编译，不复用
  旧 tmp/sstate/生成库。工具链别名和原空 nosys.specs 必须恢复，已纳入准备步骤。
- 当前完整镜像干净重建尚未通过；上传与新 GitHub 克隆验证结果后续写入
  `repro-inputs/rk3572/tests/clean-rebuild.md`。M7 外设直驱及历史 Stage 03–05
  每阶段完整独立层缺失限制仍在，不能把归档补齐称为这些功能验收。

## 2026-09-28：换机输入已上传，固件与离线取源通过，完整镜像编译中

- 已推送 GitHub main：`9e0451e`、`f2e9887`、`4a8c099`、`7e59de6`、
  `173bb38`、`e88a230`、`5655fb0`。原 M7 的日志/RPC 修复/实机证据已随任务上传；
  这不是 M7 工业外设验收。
- 最终补充四个输入归档共 550,848,503 B（525.33 MiB）：150 个 openEuler 包目录、
  17 个上游下载源文件/源码 Git 镜像（含原缓存中的 neard、erofs-utils）、
  完整 M6 有效 UniProton 覆盖（含 libboundscheck、适配后的 lwIP 2.1.3）、
  yocto-meta-openeuler 单提交浅 Git 元数据（没有 remote/hooks/凭据）。
- Git 元数据恢复需创建空 `.git/refs` 并 `read-tree HEAD`；源码提交必须是
  `3aa6999c9ab78569bc2209a9dbb185e2f7e4301c`。Yocto 入口需 source Native SDK
  环境，不然 compile_et 缺失。工具链命令别名、空 nosys.specs 已在准备脚本恢复。
- 全仓库当前实际文件约 3.247 GiB / 3.486 GB；用户选择固定 Docker 摘要联网拉取，
  不上传另一个 11.16 GiB 展开的基础镜像。密码/Token/SSH 私钥/board core 不上传。
- Windows 独立验证克隆：`C:/Users/limew/AppData/Local/Temp/rk3572-github-verify-20260928`，
  Git LFS 3.7.1；四个归档、清单、完整内核与工具链从 GitHub 下载后哈希一致。
- 构建机仍 `10.100.60.226`，原 `dev_openeuler` / 原项目未做清理。
  独立验证父目录在宿主机卷下 `_data/tl3572-github-repro-20260928`；
  通过原 dev 容器查看为 `/home/openeuler/build/tl3572-github-repro-20260928`。
- Linux 克隆最初 `repo`，旧 Git LFS 2.10 的已校验 hydration 文件在 Git 看来 dirty，
  更新 downloads 归档时 ff 被拒绝；没有 reset/checkout 覆盖。重新从 GitHub 克隆
  到 `repo-v2`（commit 5655fb0），用哈希严格匹配的源文件缓存注入全部 21 个 LFS 输入。
  所有编译容器 source 只读、新工作卷、network none，不挂载旧 tmp/sstate/sysroot/.a。
- `tl3572-repro3-20260928` / `work-v3`：M6/M7 四份 ELF 从头编译全部成功，
  SHA256 分别为 9c5e55a...、3357eb97...、e42b1a37...、d5146136...，与实机版本
  完全相同。完整哈希见 `repro-inputs/rk3572/tests/clean-rebuild.md`。
- 正在运行：`tl3572-repro4-20260928` / `work-v4`，挂载 `repo-v2` 只读，REPRO_JOBS=16。
  prepare=0；离线 fetch **224/224、0 个复用、全部成功**；随后 2920 任务的
  M6 完整镜像正在编译，成功后自动继续 m7-mcs。尚未宣布全镜像通过。
- 镜像卷根日志 `prepare.log`、`fetch.log`、`m6-image.log`、后续 `m7-mcs.log`；
  固件卷根日志 `m6-up.log`、`m7-up.log`。用 `docker exec` tail/grep 状态。
  父目录的 work / work-v2 是先前检查失败的隔离目录，保留诊断，不要混用。
- 板卡 `192.168.2.141` 本次未访问/未刷写/未重启；外设仍未移交。
- 最新验证文档正在本地更新，需在任务结束前提交/推送，并核对 origin/main。

## 2026-09-28：RK3572 换机复建验证完成（取代上一节“编译中”状态）

- 当前构建全部必需输入已上传；固定源码提交为
  `5655fb00c59f1cbfce83ca4a6dd91ba5ea703fdc`。换机入口固定此提交与 Docker 摘要，
  后续 main 继续开发不影响重现本次输入。最终日志/说明另行提交到 main。
- 在 `tl3572-repro4-20260928` / `work-v4` 的新目录、固定基础镜像、只读 repo-v2、
  network none 条件下完成：prepare=0、离线 fetch=224/224、M6 镜像=2920/2920、
  M7 MCS 包=147/147，所有返回码为 0。初始 sstate 为
  Wanted 1329 / Local 0 / Mirrors 0 / Missed 1329 / Current 0，没有原工作区编译缓存。
  镜像的 224 个复用任务是本轮先做的 fetch；M7 包的 131 个复用任务来自刚完成的本轮 M6。
- M6 主日志有 6 个上游 patch-fuzz/QA WARNING，M7 包有 2 个 mcs-linux patch-fuzz WARNING；
  原始内核、UniProton、UMT 编译警告均保留，不宣称零 warning。
- M7 Yocto 实际编译的 rpc_backend.c、rpmsg_rpc.c 与板卡回归源码哈希完全一致。
  又在新工作区用新编的 libmetal/OpenAMP/sysfsutils 跑 Stage07 的
  prepare_m7_mcs.sh + build_m7_micad.sh，独立 daemon 编译返回 0，SHA-256 为
  `40b7791d55ea58edb92d0119bd985ad560b2d3e1a1eba26ed1aa6566f907d20c`，
  与板卡已回归的修复版完全一致，PIE/RELRO/NOW/栈保护、无 RPATH 确认。
- work-v3 的四份 UP ELF 与 work-v4 的独立 micad 均达到实机参考版本逐字节一致。
  当前 M6 kernel/FIT/rootfs 成功重建，但不承诺与历史镜像逐字节一致。
- work-v4 镜像产物在项目内 `build/build-tl3572/tmp/deploy/images/tl3572-evm/`：
  Image 40,081,920 B，boot FIT 40,647,168 B，mcs_km 98,472 B；
  rootfs.ext4 逻辑大小 4 GiB（稀疏），rootfs.tar.gz 90,220,064 B。
  新镜像未上传到 GitHub，上传的是可重建的完整输入和验证过程。
- 最终证据在 `repro-inputs/rk3572/tests/clean-rebuild.md` 与 `tests/logs/`：
  prepare、fetch、M6/M7 UP、M6 image、kernel compile、kernel artifact hashes、rootfs 包清单、
  M7 MCS 总/补丁/编译日志、独立 micad 日志；12 个证据文件均有 SHA256SUMS。
- 全仓库文件约 3.25 GiB / 3.49 GB；新增四个输入归档 525.33 MiB。
  用户选定 Docker 摘要联网拉取，11.16 GiB 展开镜像不额外上传；凭据和 board core 不上传。
- 构建均已结束，不要重复启动“尚在进行”的镜像任务。新验证目录/容器及原项目都保留；
  本轮没有访问、刷写或重启板卡。M7 RPM 未部署，也未替换进此次 M6 rootfs。
- 复建是在同一宿主机的全新隔离容器完成，不声称已换另一台物理主机实测。
  历史 Stage 03–05 未修改的独立层快照缺失、M7 外设直驱未完成/未验收、
  MCS create/rm fd 遗留问题与 mcsctl 错误返回问题仍在，不因本次构建通过而改变。

## 2026-09-28：全 Stage 源码已补齐上传，独立恢复及 M5 重编完成

- 用户进一步要求“应把所有 stage 的源码内容完整上传”，最新“继续”是继续这项上传任务，
  不代表继续外设驱动实施或授权板卡操作。本轮没有访问、重启、刷写板卡。
- 完整源码归档已推送 main，提交 `e637d3066d30ab14d8ebde304bd7654cedf4b80e`。
  最终脚本修正和验证证据提交为 `2e6074a506111b301ffc146650ef15966da47bf5`；
  `repro-inputs/all-stages/README.md` 的换机命令固定后者，不随 main 漂移。
- 新入口 `repro-inputs/all-stages/` 有 19 个源码/阶段配置包，共 875,528,534 B：
  M4/M5/M6 完整有效 6.12.69 内核（各 92,283 个文件/链接）、M5/M6/M7 完整 UniProton
  （12,511 / 12,776 / 12,776 个文件/链接）、Stage02–Stage07 完整 MCS（各 83 文件）、
  独立阶段层/配置以及合集。共享的完整源码/大资产按路径与 SHA-256 引用已有实际归档，
  恢复时校验并补齐，不是只上传补丁，也不依赖原容器内未归档目录。
- 另上传完整 openEuler 5.10 内核，提交 `920880cbeb4a3390da6f9e95508b29abbf45140d`，
  73,335 个跟踪源文件、192,274,017 B。Stage02 离线取源确实需要这个内核来源。
  `SOURCE-INVENTORY.json` 和 `historical/HISTORICAL-INVENTORY.json` 记录逐文件哈希，使用 LFS。
- Git LFS 实际新增上传 20 个去重后对象，约 1.1 GB；新增目录约 1.06 GiB。
  全仓库当前实际文件约 4.31 GiB / 4.63 GB，不是 Git/LFS 所有历史缓存占用。
  基础 Docker 仍固定摘要联网拉取，不上传约 11.16 GiB 展开的镜像，遵守用户选择。
- 在独立 Windows 克隆 `C:/Users/limew/AppData/Local/Temp/rk3572-github-verify-20260928`
  从 GitHub 下载 all-stages 全部 LFS 输入；没有向此克隆注入构建机源缓存。
  新归档/清单 21 项加历史输入 3 项，共 24 项 SHA-256 全部一致；`git lfs fsck` 通过。
- 七阶段均从新目录、固定摘要容器、只读源码挂载、network none 独立恢复成功。
  Stage01 只有基线审计，没有固件目标；Stage02 fetch=215/215，Stage03=217/217，
  Stage04/05/06/07 各 224/224，均为 0 个复用、全部实际执行成功。
- M5 最终全新容器 `tl3572-all-stage05-20260928-m5-final` 的恢复、取源、重编完整返回 0；
  所有核心/依赖库从源码生成。ELF 589,064 B，SHA-256
  `3faa550c98c18a407e1a2816b3c022c82fc91d85b3fb968b83ffed32631478d0`，
  与历史 `stages/stage05-uniproton/firmware/rk3572-uniproton-final.elf` 经 cmp 逐字节一致。
  入口补充 mkdir include，并保留历史 CMake `build/rk3572_mica` 路径以固定 DWARF。
- M5 正式 boot 的 IKCONFIG 与保留的 M4 正式内核配置逐字节一致，SHA-256
  `57e11529b3d8760c13eb0fa0093aa325157d59bd4176deea6f6198afd26b718d`；
  使用 `maxcpus=7`，不能把 M6 的 CPU4/5 预留政策错误套入 M5。
- 最终原始证据在 `repro-inputs/all-stages/tests/logs/`，20 个文件均有 SHA256SUMS；
  说明在 `tests/verification.md`。Linux 4 项归档单测、Python/Bash 语法检查通过。
  Stage01/03/04/06/07 批处理均完成并打印 PASS 后，因运行时覆盖驱动文件导致收尾返回 2；
  原日志 `driver-rest.log` 如实保留，不把批处理整体冒充 exit=0。当前脚本语法通过，
  随后新目录 M5 驱动完整 exit=0；后续不要在运行中覆盖驱动。
- 构建宿主卷 `_data/` 中新增验证目录为 `tl3572-all-stages-validation-20260928`、
  `tl3572-all-stages-validation-rest-20260928`、`tl3572-all-stages-validation-m5-final-20260928`；
  输入导出目录为 `tl3572-all-stages-history-v2-20260928`、
  `tl3572-all-stages-snapshots-v2-20260928`，证据副本在 `tl3572-all-stages-evidence-20260928`。
  这些均已结束，原项目、原容器、新测试目录及首轮诊断目录均保留，勿重复启动旧任务。
- Stage03–Stage05 未修改的独立完整历史层没有幸存；新增独立层是有证据的重建版，
  不是原始逐字节历史层快照。历史清理的 M5.1/M5.2 临时工作树无法补造。
  本轮未重编 Stage02–Stage05 的每份全镜像，也未换另一台物理主机实测。
  此前已通过的 M6 全镜像、M6/M7 ELF、M7 MCS/micad 验证见上一节，不重复冒充新测试。
- M7 上传的是已实现的日志/RPC 软件；外设移交和直驱仍未实现/未验收。
  MCS create/rm fd 和 mcsctl 错误返回遗留问题不变。旧 tmp/sstate、大型生成镜像、
  密码/Token/私钥/board core 不上传。整个原厂 LinuxSDK/dl/sysroot 包不属于此 openEuler
  Stage 构建输入，仍不上传；用到的厂商源码、工具链和资产已经单独归档。

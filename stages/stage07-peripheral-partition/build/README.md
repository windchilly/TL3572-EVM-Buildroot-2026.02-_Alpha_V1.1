# M7 构建输入与 RPC 修复复建

在固定 M6 构建环境内执行；不能仅靠 Stage07 目录从空系统重建完整镜像。M6 上游源码、工具链和 Yocto 环境的准备步骤见仓库根目录 `repro-inputs/README.md`。

2026-09-28 增加[换机、空目录构建入口](../../../repro-inputs/rk3572/README.md)：
它补齐 libboundscheck 与所有 openEuler 包输入，并从源码构建 UniProton 库；
`m7-mcs` 通过 Yocto 重建依赖和 MCS 包。下文的独立 daemon 快速构建仍要求
已有 M6 sysroot，不等同于该干净构建入口。

## 独立 micad 复建

默认项目根目录 `/home/openeuler/build/tl3572-2oo3`，其中应已有未打补丁的固定 MCS 源码 `src/mcs`（提交 `5cb49156276be04d54a77a630b8600dcc122fdba`）、Arm GNU 14.3 `toolchain-14.3` 及 M6 构建留下的 `build/build-tl3572/tmp/sysroots-components/aarch64/{libmetal,openamp,sysfsutils}`。

在完整仓库克隆内运行：

```sh
bash stages/stage07-peripheral-partition/build/prepare_m7_mcs.sh
bash stages/stage07-peripheral-partition/build/build_m7_micad.sh
```

准备脚本复制上游源码到独立的 `src/mcs-m7`，应用原 M6 的两份补丁及 M7 的 `0003`，不会修改上游目录或 M6 层。若目标目录存在则拒绝覆盖。构建输出默认是 `build-micad-m7/mica/micad/micad`，保留 PIE、RELRO/NOW 和栈保护，并带调试信息；现有上游 UMT 代码仍有一个未使用变量 warning。

可通过 `PROJECT_ROOT`、`MCS_BASELINE_ROOT`、`MCS_ROOT`、`TOOLCHAIN_PATH`、`SYSROOT_COMPONENTS`、`MICAD_BUILD_DIR` 调整路径。记录中的第二次源码准备与编译使用 `mcs-m7-reprocheck` 及 `build-micad-m7-reprocheck`；两个源码树逐文件一致，含调试路径的 ELF 不要求跨构建目录哈希一致。原 M6 依赖库没有重新安装到板卡。

## Yocto 集成边界

`source/yocto/meta-tl3572-m7` 是补充层，依赖原 `meta-tl3572-stage3` 的 `tl3572` collection，只为 `mcs-linux` 增加 `0003`。把本补充层加入**独立 M7 构建配置**的 `BBLAYERS`，保留整个 Stage07 的目录层级；补丁仍从同一份 `source/patches/mcs` 引用。不要单独复制 bbappend 后丢失这个相对路径。

早期只验证元数据解析及独立 daemon 编译。2026-09-28 的[空目录重建检查](../../../repro-inputs/rk3572/tests/clean-rebuild.md)
已通过 M6 镜像 2920/2920 和 M7 MCS 软件包 147/147，实际生成 RPM；独立部署版
micad 也使用本轮新编的依赖库重建，并与实机修复版哈希完全一致。仍未重打完整 M7 镜像，
未把新 RPM 部署到板卡。在已有环境中临时检查新增层解析时，仍可使用
`tests/m7-yocto-parse.conf`（先按实际克隆位置调整其中路径），配合：

```sh
bitbake -r /absolute/path/stage07-peripheral-partition/tests/m7-yocto-parse.conf -e mcs-linux
```

必须同时确认 `BBFILE_COLLECTIONS` 包含 `tl3572m7`，`SRC_URI` 包含 `0003-rpc-shared-log-lifecycle.patch`，且 `FILESPATH` 指向实际补丁目录。仅在 `BBLAYERS` 字符串中看到路径不代表层已加载；后读取选项 `-R` 不适合这个验证。

## 板卡部署与回退

本轮板卡部署采用独立文件 `/usr/libexec/m7/micad` 和持久 drop-in `/etc/systemd/system/micad.service.d/90-m7-rpc-fix.conf`，原 `/usr/bin/micad` 未覆盖。drop-in 内容来自 `source/host/micad-m7-rpc-fix.conf`。服务仍使用原 PIDFile、MCS 内核模块前置依赖及失败重启策略。临时 M7 配置为 `AutoBoot=no`，没有安装为开机自动启动实例。

需要回退时，先停止所有 UP 实例，并用 `tests/board/query_cpu_off.py 4 5` 确认两 CPU 真正 OFF；然后仅移走上述 `90-m7-rpc-fix.conf`，执行 `systemctl daemon-reload`、`systemctl restart micad`，服务即恢复 `/usr/bin/micad`。不要移走原 `10-mcs-km.conf`。若任一 CPU 未 OFF，不能用守护进程重启代替板卡恢复，也不要继续测试旧版已知有问题的双停止路径。

回归脚本 `tests/board/regress_micad_rpc_lifecycle.py` 需要在板卡上与 `query_cpu_off.py`、Stage06 的 `tests/dual-runtime-regression.py` 放在同一目录（或用 `--echo-helper` 指定）。先创建两份临时 M7 配置并保持 Offline，再执行脚本；它覆盖两种停止顺序及交替启动、真实 RPMsg 回显、进程 PID/自动重启数、PSCI OFF、共享日志 fd 数及离线 fd 基线。失败时中止，不会自动重启板卡或在异常状态继续压测。

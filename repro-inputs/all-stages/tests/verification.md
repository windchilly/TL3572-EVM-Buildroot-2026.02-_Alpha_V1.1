# 全阶段源码验证记录（2026-09-28）

## 已完成的归档验证

- 七个阶段的来源/输入映射保存在 `../STAGES.json`。
- 19 个阶段源码/配置归档共 `875,528,534` 字节；本目录的 21 项 SHA-256 全部通过。
- 额外完整 openEuler 5.10 源码包为 `192,274,017` 字节、73,335 个跟踪源文件，
  提交 `920880cbeb4a3390da6f9e95508b29abbf45140d`；历史输入的 3 项校验全部通过。
- M4/M5/M6 完整有效内核各有 92,283 个文件/符号链接；补丁均先 `git apply --check` 再应用。
- 完整 UniProton：M5 12,511 个文件/链接，M6/M7 各 12,776 个；包含实际依赖源码，未复用旧构建库。
- 完整 MCS：Stage2–Stage7 各 83 个文件；M5/M6/M7 分别应用对应阶段补丁。
- M5 正式 boot 的 IKCONFIG 与保留的 M4 正式内核配置逐字节一致，CPU 政策为 `maxcpus=7`。
- Linux 上归档工具 4 项单测通过：确定性、保留合法相对链接、拒绝越界链接、拒绝未解析 LFS 指针。
- Python 与 Bash 脚本语法检查通过；最终 Bash 脚本的 SHA-256 及 Linux 单测结果见
  `logs/scripts-validation.log`。

## 独立恢复验证

七个阶段均已从新目录恢复，使用固定摘要容器、只读仓库挂载、`network none`。
没有挂载原项目，也没有复用旧 `tmp/sstate/sysroot/UniProton .a`。
隔离参数原始记录见 `logs/container-isolation.log`。每阶段恢复和取源日志分别为
`logs/stageNN-prepare.log`、`logs/stageNN-fetch.log`。

| 阶段 | 独立恢复 | 离线取源 | 本轮额外构建 |
|---|---|---|---|
| Stage01 | 通过 | 不适用：基线审计，无构建目标 | 无 |
| Stage02 | 通过 | 215/215 成功，0 个复用 | 无 |
| Stage03 | 通过 | 217/217 成功，0 个复用 | 无 |
| Stage04 | 通过 | 224/224 成功，0 个复用 | 无 |
| Stage05 | 通过 | 224/224 成功，0 个复用 | 全新目录重编 M5 ELF，通过 |
| Stage06 | 通过 | 224/224 成功，0 个复用 | 完整构建沿用此前独立验证，见下文 |
| Stage07 | 通过 | 224/224 成功，0 个复用 | 已实现软件的构建沿用此前独立验证，见下文 |

构建宿主机日志父目录位于：

```text
/home/docker_space/docker/volumes/dev_openeuler_vol-openeuler-build/_data/
  tl3572-all-stages-validation-20260928/             # Stage02
  tl3572-all-stages-validation-rest-20260928/        # Stage01/03/04/06/07
  tl3572-all-stages-validation-m5-final-20260928/    # 最终全新 Stage05
```

### M5 全新目录重编

最终容器为 `tl3572-all-stage05-20260928-m5-final`，完整恢复、取源和重编的驱动返回码为 0。
核心库、libboundscheck、OpenAMP/libmetal 和应用均从源码编译；未复制旧生成库。
原始日志见 `logs/stage05-up.log`、`logs/driver-m5-final.log`、`logs/m5-artifact.log`。

输出文件：

```text
/home/openeuler/build/tl3572-2oo3/src/UniProton/demos/rk3572_mica/build/rk3572-m5-rebuilt.elf
589064 bytes
3faa550c98c18a407e1a2816b3c022c82fc91d85b3fb968b83ffed32631478d0
```

与 `stages/stage05-uniproton/firmware/rk3572-uniproton-final.elf` 的 SHA-256 相同，
并经 `cmp` 验证逐字节一致。构建入口显式校验该参考哈希。

首轮准备发现历史归档不保存空 `include` 目录，已在入口显式创建。
首轮应用还使用新 CMake 目录 `m5-repro`，ELF 仅调试路径不同；去掉调试信息与 build-id 后
内容一致。改回原始 `build/rk3572_mica` 路径后，再用上述全新目录重编，完整 ELF 一致。
首轮实验目录保留，不作为最终通过日志。

### 批处理驱动说明

`logs/driver-rest.log` 如实保留 Stage01/03/04/06/07 均打印 `validation PASS` 后的
驱动收尾语法错误。该次批处理返回 2：运行过程中更新了正在被 Bash 读取的驱动文件，
导致读取位置错位；不是这些阶段的恢复或 fetch 失败，不能把批处理整体退出码写成 0。
最终驱动语法检查通过，随后新目录 M5 单阶段驱动完整返回 0。后续验证应固定脚本版本，
不要在运行期间覆盖驱动文件。

## GitHub 独立下载验证

完整源码归档已推送到 main，输入提交为
`e637d3066d30ab14d8ebde304bd7654cedf4b80e`。Git LFS 实际上传 20 个去重后对象，约 1.1 GB。

在独立 Windows 克隆
`C:/Users/limew/AppData/Local/Temp/rk3572-github-verify-20260928`
从 GitHub 执行 `git lfs pull --include='repro-inputs/all-stages/**' --exclude=''`。
没有向该克隆注入构建机源缓存。本目录 21 项、historical 目录 3 项，共 24 项 SHA-256
全部一致，工作树干净。原始校验记录见 `logs/github-readback.log`。

本轮新增目录约 1.06 GiB；全仓库当前实际文件约 4.31 GiB / 4.63 GB。
这是当前检出的实际文件量，不是 Git/LFS 全部历史缓存的磁盘占用。

`logs/SHA256SUMS` 校验 20 个证据文件。日志保留原始编译警告，不声称零 warning。

## 验证边界

此前 M6 全镜像（2920/2920）、M6/M7 四份 ELF、M7 MCS/独立 micad 的完整干净构建结果
见 `../../rk3572/tests/clean-rebuild.md`。本轮新增的是各阶段独立恢复/离线取源及 M5 重编，
没有重编 Stage02–Stage05 的每份完整历史镜像，也没有宣称这些镜像逐字节相同。

本轮不访问、重启或刷写板卡，原项目和原容器保留。复建在同一宿主机的新隔离容器完成，
不是另换一台物理机实测。Stage03–Stage05 的层为有来源记录的重建版，
不是原始独立历史层快照；被历史清理的中间工作树无法补造。
本记录冻结的 9 月归档中，M7 上传的是已实现的日志/RPC 软件，当时外设直驱尚未实现/验收。
后续 main 中 CAN 轮询及 2026-10-09 自主配置/IRQ 的源码与验证另见
[CAN IRQ 实机记录](../../../stages/stage07-peripheral-partition/tests/board/can-irq-20261009/README.md)。
这些新结果不回写历史归档，完整外设移交仍未验收。

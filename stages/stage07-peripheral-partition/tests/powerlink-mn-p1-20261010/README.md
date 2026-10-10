# POWERLINK MN P1：EDRV 软件基线（2026-10-10）

本轮承接 UP2/CPU5 做 MN、ETH2 直驱的已确认需求。**软件基线通过，P1 硬件验收未完成**。
没有连接板卡/COM7，没有改 PHY、解绑网卡、发送物理帧、重启或部署候选。
正式 `firmware/` 两 ELF 的 SHA 仍为 `8bfb824b...` / `627545f5...`；原 M6/DT 不变。
CAN/UART“接线改变，先不要发送”继续有效。

## 实现范围

- 新增真实 `edrv-rk3572.c`，实现上游要求的 9 个 EDRV 接口。
- 8 项 TX 描述符（最多同时占 7 项，保留一空位）、8 项 RX 描述符，32 个独立 TX 缓冲区；
  每缓冲区 1536B，总 DMA 布局 61696B，位于 UP2 已有 `0x7ca10000` 64KiB Normal-NC/RW/XN 窗口。
- 缓冲区身份校验、池耗尽、重复分配/释放、DMA 占用时拒绝释放或重复提交；
  仅在 OWN 清除且无错误时完成回调，回调中可以释放/重发。TX 错误不会伪报成功。
- 8 项组播地址、32 项软件接收过滤（22B value/mask + enable）；MAC 接收全部组播，
  软件严格检查目的 MAC 和已启用过滤器，不用 Linux 网卡代理。
- 有限工作量轮询，无每帧 TaskDelay。RX 同步回调后归还描述符；MAC ACS/CST 关闭，
  接收长度统一减去 4B FCS。错误、碎片、上下文描述符和非法长度丢弃并计数。
- 异常延迟释放请求明确失败并保留 RX 数据，须 reset；发送 launch-time、自动回应、
  per-filter handler、deferred RX 编译配置不受支持时直接编译失败。
- 停止先阻止新提交，DMA 复位成功后才撤销缓冲区。复位失败保持 FAULT、缓冲区和资源 lease，
  禁止再次启动/释放，不能卸载宿主电源/根时钟保持模块。
- BSP 复用原 own clocks/mux/MDIO/vendor PHY 配置，增加 forced 100-half / AN-off、
  PHY BMCR/BMSR 与 MAC half-duplex 能力和配置回读检查；保持原 100-full 测试参数。
  所有新增 BSP 入口只编译到 UP2；UP1 不添加 GMAC 映射。
- legacy ETH 测试与 EDRV 增加互斥 lease；共享根 gated 时拒绝 GRF/MAC 访问。
  Linux unbind + V3 host power/root hold 仍是外部强制前提，UP2 的软件 lease 不会代替宿主移交。

这些能力尚未执行 MMIO/PHY，不能据编译结果称半双工可靠或驱动物理收发通过。

## 实际验证

最终输入对应 `build-checked-final.log` / `build-checked-repro.log`：

1. 原 P0 核心 2 组 native NMT/OD 测试通过，72 个上游 C 核心库 SHA 保持不变。
2. 新增 9 组真实 EDRV C 测试通过：初始化及失败清理、32 缓冲区身份/耗尽、7-in-flight 环回绕、
   回调重发/释放、TX 错误及 DMA fatal、停止失败保留、组播/过滤更新/预算、RX 错误/长度/FCS、
   意外延迟释放。只有 BSP/MMIO 与 DMA 完成由内存模拟；不调用假的 EDRV 实现。
3. Windows 和固定容器各 73 项 Python 回归通过；原生累计 parser、18 组调度/生命周期、3 codec 通过。
4. EDRV AArch64 本地代码使用 `-Wall -Wextra -Werror`；核心+EDRV 合并审计：9 EDRV 已定义，
   21 HAL + 8 libc 未解析，无 FP/SIMD/Linux/socket/pcap/pthread/libatomic 依赖。
   21 HAL 中的 5 项 BSP 在单独真实 UniProton 编译审计中全部解析，剩余项是 P2 target/cache/timer。
5. `build-candidate-final.log` / `build-candidate-repro.log`：两份累计候选编译和 ELF 审计通过；
   页表 UP1 9/16、UP2 10/16。强制合并 EDRV+BSP 对象，防止最终 gc-sections 删除未引用代码后误称链接已验证。
   14 接口全部有实现，只有 PRT_Printf/PRT_TaskDelay/memcmp/memcpy/memset 未解析，无 FP/SIMD/原子运行库。
6. 两独立目录的核心 `.a/.o`、EDRV `.a`、核心+EDRV `.o`、两候选运行镜像均逐字节一致。
   ELF 调试路径不要求一致；完整 SHA/字节数见 `repro-report.json`。

EDRV 库 13722B，SHA `c576132cd1a83b22e056c5d348b46e8c329648fbaa176a84b71968cb6e8f6ef8`。
候选 UP1 运行镜像 SHA `074cdb3a020d463a2203a7163e8b59a1329c4e0dce920f0055b1e65d928f64cf`；
候选 UP2 SHA `a6946bf8ff4e8061d3072bef43fa6222e0420b4f0ddfe7e708c39349eb3bca96`，**不是已实测正式 UP2**。

源码/证据保存在服务器容器 `/home/openeuler/build/powerlink-mn-p1-20261010/stage`；
最终软件构建为 `build-checked-final` / `build-checked-repro`，累计候选为
`UniProton-candidate-final` / `UniProton-candidate-repro`。不覆盖 M6 树或实测 V3 树。

早期失败完整保留：`build-first.log` 缺 trace include 路径；`build-candidate-first.log`
两 ELF 已编译但强制合并用了错误 `.obj` 后缀；均已修复并全新目录重跑，不删失败证据。
旧上游 99 条核心编译警告，以及 M6 endian/RWX 等已有警告仍在日志，不是零警告。
固定环境无 ASan/UBSan，因此没有 sanitizer 验证结论。

## 换机复现入口

按仓库固定 Docker 摘要准备环境、执行 M6 复现取得原 UniProton 树及工具链，再在容器中：

```bash
export TL3572_PROJECT=/home/openeuler/build/tl3572-2oo3
export TOOLCHAIN_PATH=$TL3572_PROJECT/toolchain-14.3
export POWERLINK_BUILD_ROOT=$TL3572_PROJECT/build-powerlink-p1-first
bash stages/stage07-peripheral-partition/build/build_m7_powerlink_edrv.sh
export UNIPROTON_ROOT=$TL3572_PROJECT/src/UniProton-powerlink-p1-first
export OPLK_SOURCE=$POWERLINK_BUILD_ROOT/core/source/openPOWERLINK_V2-2.7.2
bash stages/stage07-peripheral-partition/build/build_m7_powerlink_candidate.sh
```

选择新的第二组输出路径重复以上流程；用 `tests/compare_powerlink_p1.py` 按顺序传入两软件构建根、
两候选源码根和 report.json 输出路径。脚本拒绝覆盖已有构建/源码目录。
上游完整归档/锁定不变，无需上传 Docker 展开内容；候选 ELF 不替换正式交付、也不作为硬件验收点。

## 尚未完成 / 下一入口

- 必须先验证 MAC/PHY 与隔离对端的 forced 100-half 实机收发、FCS 长度和 DMA 启停；
  旧 100-full L2 结果不能代替。ETH3 USB/Linux 对端只能用于开发测试。
- 本轮是轮询基线，没有 IRQ 实时调度、时间戳、拥塞/掉线恢复、最坏延迟或周期抖动结论。
- 当前 EDRV API 要求单 UP2 owner 串行调用；回调禁止递归 init/exit/poll。
  P2 必须解决高精度 timer/ISR 与 stack/EDRV 的临界区，不能直接并发调用。
- 32 TX 缓冲区不是 32 个 CN 的保证，MN 控制帧与双缓冲也会占池；P3 须做节点数/内存预算。
- P2 target/cache/high-resolution timer 仍未实现，P3 MN/OD/CDC/应用任务仍未接入，
  没有 POWERLINK run 命令，不能控制 CN/伺服；无 CN 对端互操作或工业验收。

依据：[上游 EDRV 接口](https://github.com/OpenAutomationTechnologies/openPOWERLINK_V2/blob/V2.7.2/stack/include/kernel/edrv.h)、
[Linux DW MAC 描述符](https://github.com/torvalds/linux/blob/v6.6/drivers/net/ethernet/stmicro/stmmac/dwmac4_descs.c)、
[Linux stmmac 环形队列/FCS 处理](https://github.com/torvalds/linux/blob/v6.6/drivers/net/ethernet/stmicro/stmmac/stmmac_main.c)。
参考的是接口/硬件语义，没有把 GPL Linux 实现源文件链接进 UP2。

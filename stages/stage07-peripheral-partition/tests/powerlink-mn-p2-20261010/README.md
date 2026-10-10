# POWERLINK MN P2：UniProton target / cache / 高精度定时软件基线

日期：2026-10-10。用户要求继续 UP2 MN，通过 ETH2 直驱控制外部设备。
**本记录只证明软件实现、编译和静态/原生测试，不是定时器硬件、实时性或可运行 MN 验收。**
未连接板卡/COM7，未执行系统寄存器/PHY/MMIO、发送帧、解绑、部署或重启。
正式两累计 ELF 的 SHA 仍为 UP1 `8bfb824b9f73967add8d27535bc275f9bcbb9dbbdb671ffaf3bf83edf375d14c`、
UP2 `627545f53ffba3d876973371042c70174c254734f433f01afc1b47578057e660`；原 M6/DT 不变。
CAN/RS-232/RS-485“接线改变，先不要发送”仍有效。

## 本次实现及边界

- 只新增 P2 文件/0012 补丁；P0 72 源码核心和 P1 EDRV 的固定构建输入不改。
  P0/P1 旧记录和 SHA256SUMS 保留在其固定 Git 提交；其中 README/memory 等动态入口的旧哈希
  不应拿来校验当前新增版本。P2 的当前输入以本目录 SHA256SUMS 为准。
- `target-uniproton.c`：唯一 UP2 task owner，真实 RTOS count-1 信号量支持 8 个 task-only 非递归互斥量，
  不阻塞竞争、不承诺优先级继承；无效/重复释放、锁定时销毁、RTOS 失败保持错误/FAULT。
  临界区嵌套保存并恢复进入时 IRQ 屏蔽状态，不无条件开启中断；不在屏蔽 IRQ 的上下文阻塞/调度。
  Tick 以毫秒提供，睡眠向上换算到系统 Tick。现有 libc `malloc` 复用默认 FSC / PRT_MemAlloc，
  没有新增跨实例 heap；只静态核验真实 RTOS/libc 符号，尚非上板分配/耗尽测试。
- `rk3572_powerlink_rtos.c`：UP2 cacheable image `0x7c200000..0x7ca00000` 执行 CTR_EL0
  cache-line 的 DC CVAC / CIVAC + DSB；CIVAC 保留本地 CAL 的脏邻接字节。
  精确 Normal-NC DMA `0x7ca10000..0x7ca20000` 只需要屏障；拒绝 UP1、页表、其他共享/外设地址、溢出范围。
  不适用于多核缓存共享或 cacheable DMA alias，不替代 EDRV 的描述符所有权协议。
- UP2 本核 **CNTP / PPI30（PPI14）**，两个逻辑 timer 共用绝对 CNTP_CVAL。
  UniProton 原 **CNTV / PPI27（PPI11）** 的 1ms Tick 完全不改，无新增 MMIO/PTE。
  使用实际 CNTFRQ，ns->tick 向上取整；0/非法频率/超 INT64_MAX tick 拒绝。
  句柄含递增 generation，跨删除/重启不复用旧代次；64bit counter wrap、one-shot、周期和先后到期处理。
  超期周期跳过，不突发补发；记录 callback/IRQ/跳期/最大迟到，计入前一回调耗时。
- **ISR 只关 CNTP / 计数，绝不直接调用协议栈或 EDRV**；`m7_hrestimer_process()`
  由同一个 owner task 串行调用，单次最多两个已到期回调。支持回调改/删 timer，拒绝递归 process/exit。
  回调错误、非法 void 操作或试图开启未实现 extSync 会锁 FAULT 并关 timer；不假装支持外部同步。
  当前没有任务运行循环或 ISR 唤醒调度保证，P3 必须连续、有界地泵送；1ms TaskDelay 不能用于周期循环。
- 只在 CPU5/EL1/固定非 SMP/GICv2 上编译平台；要求本核 PPI30 已属 Group1、level、禁用且无 pending/active，
  CNTP 未启用。只写 PPI30 banked enable/pending 位与自己的 priority 字节，不改 group/config/distributor全局配置。
  检查失败拒绝启动，不接管其他注册/运行中的 timer；EL2 访问权限不能在 EL1 静态证明，仍须上板确认。
- 固定源码的通用 PPI disable/delete 路径使用 GICR 地址，而 RK3572 demo 使用 GICv2。
  **不调用 PRT_HwiDisable/Enable/Delete 处理此 PPI**；第一次成功注册后保留 handler 直到固件重启，
  停止时关 CNTP/PPI30、清本位 pending、检查 inactive、恢复自身 priority。
  停止失败保留 lease/FAULT；该“停止”不表示向其他业务注销归还 PPI30。
- 非 SMP `g_uniFlag` + 固定 flags 是唯一显式私有 context ABI，用于拒绝任何 HWI/Tick/System/Exception。
  0012 的编译检查和 `audit_powerlink_rtos_abi.py` 核验固定 flags / libRK3572.a 实现；换 kernel/SMP 必须重新适配。
  上游 PDO 有忽略 lock 返回值的调用，故 **P3 必须在所有公共 stack/EDRV 入口先做 owner/ready 检查**；
  仅靠互斥量返回错误不能允许多任务或 ISR 并发进入栈。

## 验证结果与原始证据

最终输入为 `checked-final-v2.log` / `checked-repro-v2.log`，累计候选为
`candidate-final-v2.log` / `candidate-repro-v2.log`：

1. P2 的 12 组 C 测试全部通过：ceil/溢出换算、占用及停止失败、双到期及 counter wrap、
   周期超期跳过、回调自重设/删另路/递归拒绝、慢回调迟到、陈旧句柄与容量、错误/外同步、
   mutex生命周期/资源耗尽、嵌套 IRQ/原状态保留、cache归属/范围、owner/ISR/IRQ屏蔽拒绝。
   使用真实 P2 源码，只有 RTOS/寄存器边界被模拟，不能证明物理 IRQ/cache/EL2 行为。
2. 原 P0 NMT/OD 2 组、P1 EDRV 9 组 C 测试通过。
   Windows/Linux 各79项 Python 通过；原生 parser +18组调度/生命周期 +3 codec 回归通过。
3. 本地新 C 使用 `-Wall -Wextra -Werror`，A53/general-registers-only/strict-align/no-outline-atomics。
   全部核心+EDRV+target/timer 强制合并，P0 的 25 个 HAL 均真实定义；软件对象仍有22平台+BSP及8libc依赖。
4. 累计候选默认 OFF / UP2-only，无 MN 命令。真实 Ethernet+RTOS BSP 强制合并后，
   25 HAL /22 BSP均定义，只剩13 RTOS项（含g_uniFlag）+8libc；无 FP/SIMD/POSIX/原子运行库。
   `rtos-abi.json` 核验固定内核库提供除demo PRT_Printf以外的所有依赖及 PRT_MemAlloc/Free。
   不把 final ELF 的 gc-sections 删除休眠代码视作完整 MN 链接或运行通过。
5. 页表 UP1 9/16、UP2 10/16；静态精确归属映射检查通过。
6. 两独立软件根/累计源码根，9个产物逐字节一致；全表见 `repro-report.json`。
   ELF/真实 BSP `.o` 包含不同调试路径，不要求其原始字节一致；BSP `.o` 仅剥离调试段后参加对比。

RTOS 库25302B / SHA `3757a3ba2807c348de48d29b5232f9f9153fed50b0c41a3841fbd1f09e8612f6`；
核心+EDRV+RTOS对象542656B / SHA `a63f52fcacc65dc3b86471b0e861ce24d9f190e0cab798ee4f74a767c4d5c7d3`。
候选 UP1 runtime360676B / SHA `074cdb3a020d463a2203a7163e8b59a1329c4e0dce920f0055b1e65d928f64cf`；
UP2 runtime382596B / SHA `59d789865b9f4b8d71a947c160fd9a9e593395abe59dad45d12a0dade4fe46f2`，**不是已实测正式 UP2**。

旧上游99条核心编译 warning、M6 endian/RWX 等既有 warning 完整保留，不是零告警/生产认证。
固定环境无ASan/UBSan，没有 sanitizer 结论。
早期 `initial.log` 是测试中 `void*` 宏的组合变量声明错误；`candidate-initial.log` 漏安装新 BSP；
`candidate-final.log` 是协议/RTOS头同时进入 BSP 引起 INLINE/TRUE/FALSE 宏冲突。
已分别修正独立声明、显式安装和只包含纯平台头，未改历史 P0 targetdefs。
`checked-final/repro`、`candidate-checked-final/repro` 是慢回调统计修正前的成功轮次，非最终输入；原始记录不删除。

## 换机完整复现

先按根目录 [全阶段复现](../../../../repro-inputs/all-stages/README.md) 与
[M6 空目录构建](../../../../repro-inputs/rk3572/README.md)恢复源码、固定 Docker 摘要、GCC14.3 与完整 M6 UniProton树/库。
Docker 联网下载固定摘要，不依赖开发服务器旧产物；上游完整归档通过 Git LFS 获取并验证。
本增量没有改变基础环境/源码包 SHA，也不需要上传展开的 Docker。
在完整仓库克隆的固定容器中执行：

```bash
export TL3572_PROJECT=/home/openeuler/build/tl3572-2oo3
export TOOLCHAIN_PATH=$TL3572_PROJECT/toolchain-14.3
export POWERLINK_BUILD_ROOT=$TL3572_PROJECT/build-powerlink-p2-first
bash stages/stage07-peripheral-partition/build/build_m7_powerlink_rtos.sh
export UNIPROTON_ROOT=$TL3572_PROJECT/src/UniProton-powerlink-p2-first
bash stages/stage07-peripheral-partition/build/build_m7_powerlink_rtos_candidate.sh

export POWERLINK_BUILD_ROOT=$TL3572_PROJECT/build-powerlink-p2-second
bash stages/stage07-peripheral-partition/build/build_m7_powerlink_rtos.sh
export UNIPROTON_ROOT=$TL3572_PROJECT/src/UniProton-powerlink-p2-second
bash stages/stage07-peripheral-partition/build/build_m7_powerlink_rtos_candidate.sh

python3 stages/stage07-peripheral-partition/tests/compare_powerlink_p2.py \
    $TL3572_PROJECT/build-powerlink-p2-first $TL3572_PROJECT/build-powerlink-p2-second \
    $TL3572_PROJECT/src/UniProton-powerlink-p2-first $TL3572_PROJECT/src/UniProton-powerlink-p2-second \
    $TL3572_PROJECT/powerlink-p2-repro.json
python3 -m unittest discover -s stages/stage07-peripheral-partition/tests -p 'test_*.py' -v
bash stages/stage07-peripheral-partition/tests/run_integrated_native.sh
sha256sum -c stages/stage07-peripheral-partition/tests/powerlink-mn-p2-20261010/SHA256SUMS
```

两个构建脚本均拒绝覆盖已有构建/源码目录。
本轮服务器容器路径 `/home/openeuler/build/powerlink-mn-p2-20261010`：
最终软件根 `build-checked-final-v2` / `build-checked-repro-v2`，
累计根 `UniProton-candidate-final-v2` / `UniProton-candidate-repro-v2`；完整源码差量、脚本与证据归档在 `delivery/`。
候选只存在开发输出根；正式 `firmware/` 未替换。

## 下一步及验收缺口

P3 接入 passive MN owner 任务、OD、内存 CDC、状态/日志、受控启动停止、资源与缓冲预算。
必须先上板只测 CNTP 权限、PPI30投递、重复启停、Tick不受影响与最坏服务延迟/漂移，
再独立验收 P1 forced 100-half 的 PHY/MAC、物理收发/FCS/DMA静默停止，才能开放网络运行。
当前没有周期发帧/CN发现/配置/PDO/SDO互操作证据，不能控制伺服，也不能承诺周期或节点数。
ETH3 USB/Linux 只是开发对端，不是工业实时验收依据；真正 MN 验收需要隔离的 POWERLINK CN 对端。

接口依据：固定归档的 `stack/include/common/target.h`、`kernel/hrestimer.h` 与
UniProton M6 `bsp/timer.c` / `cpu_config.h`、vendor `rk3572.dtsi` timer中断表；
[Arm Generic Timer 官方指南](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/Generic%20Timer.pdf?revision=c710e7a7-9f52-4901-8c9d-91b19f44f9c7)。

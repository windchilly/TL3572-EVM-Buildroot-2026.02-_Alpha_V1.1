# P3g：有界 NMT reset / NotActive / SwitchOff 软件检查点

2026-10-23，用户“继续”；本轮按上一检查点的下一步推进**软件准备**。
没有板卡 SSH/COM7、部署、ETH 移交、重启、物理 NMT reset/start、网络或 CAN/UART 发送。
正式 M6/DT/开机配置/两份累计 ELF 不变。最新硬件通过记录仍为
[P3f 栈修正版 GsOff 生命周期](../powerlink-mn-p3f-fixed-20261023/README.md)，不能把本页当作实板 MN 验收。

## 新增内容与边界

`m7_nmt_probe.c/h`、0019、`build_m7_powerlink_nmt_probe_candidate.sh`在同一累计 UP2 固件上增量接入：

1. 默认 OFF、仅 UP2；启动只创建休眠 owner，不调用协议栈初始化、prepare 或 NMT 命令。
2. COLD 显式 `PLK nmt-probe`由原单槽邮箱投递，同一 owner 执行；`PLK nmt-status`只读缓存。
3. 真实 initialize/prepare 后提交一次 SwReset，观察主站 NotActive，立即提交一次 SwitchOff。
4. 必须真实返回 GsOff，再调用一次 stop，读回 DMA/MAC/IRQ 与 timer/PPI 静默、lease0，最后 exit/COLD。
5. 每段最多32次 process，并在每次返回后检查1秒时间门槛；不是能抢占挂死栈函数的硬实时 watchdog。
6. 命令错误、错误状态、超时、收发/描述符异常、停止/静默证明失败即终止保留资源；不自动 stop/exit/重试。

不暴露任意 NMT、StartNode、持续主站循环、CN/PDO/SDO/伺服命令。保留旧 CAN/FD/串口、timer、PHY、EDRV、GsOff 诊断。
NMT reset 不是只读操作，也不继承旧无帧/有限 EDRV 帧许可；将来实板执行须新隔离窗口与独立板端 runner。
本轮 native 没有 TX doorbell/描述符使用/高精度 timer arm，不据此保证任何现场网络必然无帧。

## 故障注入实际发现与修复

首轮真实栈100次正常流程通过，但进一步覆盖 reset 新增分配位置后发现：

- 第23次分配失败：内核 PDO 共享区未创建，上游 `pdoucal_allocateMem`一直等待 NULL 指针。
  原生进程占用CPU，外层超时无法介入。按精确 PID19564/可执行路径/参数核对后仅终止该测试进程；未操作板卡。
  原始 [native-sixth.log](native-sixth.log)、[进程检查](allocation23-inspection.log)、[精确停止](stop-exact-native-hang.log)保留。
- 0006 只在 `OPLK_TARGET_UNIPROTON`分支传播同步 direct CAL 的 PDO setup 返回码；不做上游500ms等待，NULL 直接报错。
  两层都在同一 owner，睡眠不可能使失败分配重新成功；其他平台的等待逻辑不变。
- 第25次循环 TX 指针表分配失败：错误排队期间 stop/列表路径仍可访问 NULL，原生崩溃。
  [原始失败](native-patched.log)、[实际反汇编/函数定位](allocation25-inspection.log)保留。
  0007 给 UniProton 的 setNext/start/stop 三处补 NULL 返回错误，不改变其他平台。

早期 harness 链接/命名、补丁 hunk/CRLF、手工增量构建漏导出 TOOLCHAIN_PATH 的失败日志均保留。
最终 wrapper 已修正，并在第二个全新软件根从头完成；没有把首次失败改写为成功。
旧 P0/P1/P2 源码/核心配置/0001/0002/正式 RTOS 库不改，0006/0007只加入新 P3g 完整栈源码树。

## 软件验证结果

[最终原生与 Linux144项](native-final.log)、[严格set-e最终检查](software-final-checks.log)、[Windows144项](windows-tests.log)：

- 100次真实完整栈 reset→NotActive→SwitchOff→exit，2500次分配/释放配对，live0。
- 独立观测真实 nmtu 事件：`0x19→0x29→0x39→0x79→0x21c→0x0`，正常 reset/off 各5/1次处理。
- 25组真实栈场景：正常/上下文、两命令失败、两段停滞、process/PHY/stop/timer-stop/sleep/DMA/mode/readback/TX/时间超限，
  以及 reset 新增第17–25个分配位置全覆盖；旧 prepare 第1–16位置由 P3f 回归覆盖。
- 4组真实累计邮箱（probe边界mock）验证正常100轮、故障拒绝、重入不覆写/不再发送、非法命令；默认关闭入口由旧 owner 回归验证。
- 旧 P3f 29+4、P3e/P3d/P3c/P3b、P0/P1/P2/被动完整栈、累计 parser/18 lifecycle/3 codec 回归通过。

硬件/时钟/RTOS 指令由 native fixture mock；模拟时间4ms不是实机耗时或周期承诺。
没有 sanitizer 或真实堆/栈峰值证明；继承上游 endian 和 M6 RWX 等旧告警保留在日志。

## 构建与候选

Docker `dev_openeuler`，构建根 `/home/openeuler/build/powerlink-nmt-p3g-20261023`。
`software`与`software-repro`都从固定完整归档构建（第一根经历上述调试修复，第二根完整 wrapper 从头通过），本轮不是复制9个旧对象。
`UniProton-first`与`UniProton-repro`为两全新累计源树；[双根比对](repro-comparison.json)证实9个软件产物+两 runtime逐字节相同。
不同绝对路径的 ELF DWARF 不承诺完全一致。

[候选](candidates/tl3572-m7-powerlink-p3g-up-b.elf) 1,196,584B，SHA256：
`85e78eb4bb150633e695014b5ecc55401a048a2707175a031b97a2e00567f68e`。
UP2 runtime630700B，SHA `bff9f26c5e7302a763a40caf5d2753c3d146f433a59e712e3035b7f5055d28aa`；
image/BSS2160976B/8MiB，FSC512KiB，页表10/16。UP1 runtime仍360716B/d4d80d02...、页表9/16。
[审计1](nmt-probe-audit.json)/[审计2](nmt-probe-audit-repro.json)：596旧核心/OD/port/BSP全局函数全部保留，最终未解析0、LSE0。
125条继承 M6/libmetal FP/SIMD无新增，不是全 ELF 无 FPU。
[TTY栈预算](stack-budget.json)仍320B输入帧，关键链2944B+1KiB预留≤4096B；不是所有路径/IRQ最坏栈证明。

正式 UP-a/UP-b SHA仍8bfb824b.../627545f5...，没有替换。候选只归档，未上板。

## 换机复现

先恢复[固定完整 M6 源码/SDK/工具链与摘要 Docker](../../../../repro-inputs/rk3572/README.md)。
完整上游源码、端口、补丁和脚本都在仓库，不跟随远端 master。进入 stage07 后执行：

```bash
export TOOLCHAIN_PATH=/home/openeuler/build/tl3572-2oo3/toolchain-14.3
export POWERLINK_BUILD_ROOT=/path/to/new-software
bash build/build_m7_powerlink_nmt.sh
bash tests/run_powerlink_nmt_probe_native.sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
export UNIPROTON_ROOT=/path/to/new-UniProton
bash build/build_m7_powerlink_nmt_probe_candidate.sh
```

另选两个新根重做，再运行 `compare_powerlink_p3g.py 软件1 软件2 UniProton1 UniProton2 输出JSON`。
构建脚本拒绝覆盖已存在源码根，候选入口检查0006/0007已真实应用，不接受旧未修复完整栈。
`SHA256SUMS`列本轮精确输入/候选/证据；历史清单到历史 commit 验证，后验 GitHub 日志不纳入自身清单。
服务器 `delivery/`保存同一清单和日志；最终 GitHub 同步结果以最终报告为准。

下一步先准备带授权门槛、未知状态保留策略和新快照 ABI 检查的独立板端 runner，随后另获准实测。
不能沿用 P3f runner（命令白名单/快照/候选哈希不同）；不直接启动持续 MN 或连接真实执行器。

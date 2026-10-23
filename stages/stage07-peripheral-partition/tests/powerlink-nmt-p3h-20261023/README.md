# P3h：完整 PDO 内存预算与首个错误保留（2026-10-23，软件检查点）

软件修正、受限堆回归和双全新构建通过；**未部署或实测新候选**。
前一轮 [P3g 实板失败](../powerlink-nmt-p3g-hw-20261023/README.md)保持 FAILED，不改写为 PASS。
用户另行授权一次重启恢复和软件修复；板卡已恢复 Linux，当前没有新 NMT 硬件测试授权。

## 修正内容与范围

1. `m7_mn.c` 的 critical-event 和 fault 路径只保存第一个非0错误；
   process 后续的 InvalidOperation 不再覆盖 PDO 初始化失败，fault 返回该首错。
   状态结构不扩展，没有改变1504B缓存 ABI，也没有允许 FAULT 重试或自动清理。
2. 0020 增加默认 OFF 的 `M7_POWERLINK_NMT_HEAP`：只允许 CPU5/UP2 显式 NMT 候选，
   为其 FSC 堆配置1MiB；UP1、默认配置和正式固件保持512KiB。
   不减40 RX/40 TX PDO通道，不减每通道254映射上限，不改对象字典/节点配置以绕过分配。
3. 保留此前累计 CAN/FD、RS-232/485、日志、timer/PHY/EDRV/GsOff/NMT 诊断功能，默认休眠。
   没有开放持续MN/StartNode/CN/伺服控制或任意NMT命令。
4. 独立修正停止验收器的 raw CurrentEL：EL1 应为4而非1，并加入双快照拒绝1的回归。
   这个验收器错误不是 P3g stage3 堆不足的原因，也没有用于清理故障现场。

## 动态内存回归：完整真实栈 + 受限宿主分配模型

在既有真实 API/NMT/OD/PDO/EDRV/target/timer 栈测试中增加 `heap_small` 和 `heap_full`。
每个 live 请求按16B对齐后额外计64B保守开销，预留128KiB非POWERLINK占用。
这些数字是**显式压力模型**，不是实际FSC分配器、实际后台任务占用/碎片或板端峰值保证。

| 场景 | 可用总量 | 模型峰值（含预留） | 结果 |
|---|---:|---:|---|
| 旧512KiB | 524256B | 468352B | 下一块162560B请求失败；NMT0x39、首错0xb3(kErrorPdoInitError)保留、拒绝重试 |
| 新1MiB | 1048544B | 636816B | 100轮reset→NotActive→SwitchOff→COLD，分配释放配对、无泄漏 |

1MiB模型剩余411728B，并断言至少256KiB余量；并非仅把malloc改成无限大后测试。
旧实板快照则在剩148920B时申请162560B，至少短缺13640B；详见原始故障证据和交叉编译布局报告。
下一实板窗口仍须确认真实FSC总量/usage/peak及完整启停；长稳/周期PDO负载/真实CN实时预算尚未验证。

[第一根完整构建/原生回归](software-first.log)、[第二根完整构建/175项](software-repro.log)、
[最终精确输入回归](software-final.log)、[Windows175项](windows-final.log)：

- 真实完整栈27组NMT场景（新增两种堆预算）+4累计邮箱场景；原正常路径仍100轮、2500 alloc/free。
- 新受限1MiB路径另做100轮，旧512KiB路径验证实际PDO失败码不会被后续process覆盖。
- 旧P3f29+4、P3e/P3d/P3c/P3b、P0/P1/P2/被动完整栈、累计parser/18生命周期/3codec回归通过。
- Windows/Linux各175项Python：较上轮增加CurrentEL一项和P3h约束六项。

硬件/RTOS/时钟仍由native边界mock；1000us配置/模拟4ms耗时不代表实板周期能力。
无sanitizer或全程序/IRQ最坏栈证明，继承上游endian/M6 RWX等告警保留。

## 构建、候选与静态预算

Docker `dev_openeuler`，新根 `/home/openeuler/build/powerlink-nmt-p3h-20261023`：
`software`/`software-repro`都从固定归档完整构建，不复制旧预构建核心；
`UniProton-fixed-v2`/`UniProton-repro`为两全新累计树。
[逐字节比对](repro-comparison.json)确认9个软件产物及UP1/UP2两个runtime相同；ELF调试路径不承诺完全一致。

[新候选](candidates/tl3572-m7-powerlink-p3h-up-b.elf) 1,196,696B，SHA256：
`ccfba235f8f3bcc79ab0c2a0e603b2d9cc01a7f3785985566660fb1672882ea8`。
UP2 runtime630676B，SHA `a39e781aa5eaa5aa48c3508882b6e2a5c7fd9fbfbf210e0433986abd8cec42bb`。

[第一次成功审计](nmt-heap-audit.json)、[第二根审计](nmt-heap-audit-repro.json)、[栈预算](stack-budget.json)：

- 实际 ELF 的 UP2 g_memRegion00=1048576B、UP1=524288B，且实际 config.c 编译命令预处理确认初始化参数0x100000。
- UP2 image/BSS=2685248B，私有8MiB内剩5703360B；UP1 runtime保持360716B/d4d80d02...。
- 页表UP1=9/16、UP2=10/16，未改MMU容量/DDR资源分区/M6/DT/kernel。
- 最终596个旧核心/OD/port/BSP函数全保留，未解析0、LSE0；125条继承FP/SIMD无新增，不是全ELF无FPU。
- TTY输入帧320B，关键链2944B+1024B预留≤4096B；不是所有路径/IRQ最坏栈证明。
- snapshot1504/ethLease4/exception520尺寸保持；新候选仍不能用旧固定SHA runner直接运行。

初版0020给配置头的hunk上下文不足，`candidate-first.log`/`candidate-fixed.log`两次在apply检查处停止，
第二次试图忽略空白也无效；核对实际LF和先前task-count补丁后补齐完整上下文，
[标准apply检查](patch-check.log)与两全新累计树成功。[字节检查](patch-inspection.log)及原头文件inputs保留。
不是源码或工具链损坏，先前“行尾问题”的初判已被证据纠正。
Windows首次新source测试误用系统GBK读含中文UTF8补丁，`windows-tests.log`失败保留；显式UTF8后windows-final通过。

## 当前板卡与授权边界

[一次授权重启和最终复核](../powerlink-nmt-p3g-hw-20261023/README.md#后续新授权一次重启恢复不是-nmt-复测)：
boot `cd4f03d6-005d-473d-b6ce-0cc745314a08`，micad PID325/NRestarts0/active，
CPU4/5 OFF、原up-a/up-b Offline，ETH2/3 Linux100Full/ANon/linkyes，hold/临时端点消失。
板端M6固件SHA仍9c5e55a2.../3357eb97...；本地正式累计M7仍8bfb824b.../627545f5...，未替换。
失败窗口ATTEMPTED/输入/结果留存。没有再重启、部署新候选、执行reset或发送工控/测试帧，未打开COM7。

下一步只准备独立P3h板端runner/新候选SHA/ABI证明与新窗口，再另获准做一次受控NMT复测；
不得改P3g永久单次标记、把P3h塞入原root、修改旧runner的固定SHA或自动重放旧授权。

## 换机复现

先按 [完整M6源码/SDK/摘要Docker恢复](../../../../repro-inputs/rk3572/README.md)，进入stage07：

```bash
export TOOLCHAIN_PATH=/path/to/toolchain-14.3
export POWERLINK_BUILD_ROOT=/path/to/new-software
bash build/build_m7_powerlink_nmt.sh
bash tests/run_powerlink_nmt_probe_native.sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
export UNIPROTON_ROOT=/path/to/new-UniProton
bash build/build_m7_powerlink_nmt_heap_candidate.sh
```

另选两个新根重复，再执行 `compare_powerlink_p3h.py 软件1 软件2 UniProton1 UniProton2 输出JSON`。
脚本拒绝覆盖已有累计源码根；0020默认关闭且仅UP2/NMT可开启。构建脚本没有板卡访问/部署路径。
完整源码、补丁、候选、原始硬件失败/恢复与软件证据列于本目录SHA256SUMS；历史清单到历史提交验证。
`verify_powerlink_p3h_checkpoint.py`验证精确清单、18个原板端输入（旧checker查真实Git历史）、
失败未改写/重启恢复、175项和实际1355文件/0001–0007补丁，完全离线于板卡。
后验GitHub验证日志不纳入自身清单；服务器delivery保存同一清单和证据，最终同步状态以报告为准。

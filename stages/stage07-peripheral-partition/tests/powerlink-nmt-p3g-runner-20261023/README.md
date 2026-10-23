# P3g 独立板端 runner / 停核快照 ABI 软件准备

2026-10-23，用户“继续”。本检查点准备独立脚本与验证，不连接/部署/移交/重启板卡，不执行物理 NMT reset 或发送。
已另询问 ETH2↔ETH3 隔离回环和**新 NMT reset 窗口**许可；本页不是实板 PASS，不能沿用 P3f 无 reset 授权。
后续实板应建立独立日期/窗口证据，不把本页的软件结果改写为硬件结果。

## 已准备

- `tests/board/run_powerlink_nmt_probe.py`：固定候选、独立实例/配置、单次命令、只观察不重投、先证明再释放。
- `powerlink_nmt_checks.py`：纯解析/验收，不在导入时读设备；严格区分旧 GsOff 回复与新 NMT 回复。
- `read_powerlink_nmt_snapshot.py`：必须独立确认 CPU4/5 物理 OFF，才只读 UP2 私有 DRAM；不访问控制器 MMIO。
- `test_powerlink_nmt_abi.c` / `audit_powerlink_nmt_abi.py`：真实 native 和固定 AArch64 GCC 从当前头文件生成23项布局，再核对固定 ELF。
- 24项新增 Python：回复/序号/事件/旧 ABI/lease/DMA/IRQ/timer/tick/GIC/其他 probe污染、白名单/短写/重复回包、停止顺序/失败不重试、单次标记、隔离许可门槛。

候选仍为上一检查点的 **85e78eb4bb150633e695014b5ecc55401a048a2707175a031b97a2e00567f68e**，
[同一份累计 ELF](../powerlink-nmt-p3g-20261023/candidates/tl3572-m7-powerlink-p3g-up-b.elf)，本轮不修改/重编运行固件或核心。
新快照1504B，NMT结果偏移80B、大小496B、内含生命周期472B；旧 P3f 快照1008B明确拒绝。
[真实双编译器布局证明](nmt-abi.json)；TCB stride800/异常520B仍是固定 M6 私有 ABI，不把头文件证明当它们的自动发现。

## 安全顺序

固定 SHA/配置/kernel/hold → 仅原两实例Offline/物理OFF/管理口及工控快照/隔离链路100Full且ANon →
独占创建 `ATTEMPTED`永久单次标记 → hold/ETH2解绑 → 临时UP2启动与真实MMU/休眠检查 →
**只投递一次** `PLK nmt-probe` → 严格完成回包+owner缓存+工控idle → 停UP2一次 →
独立物理OFF → 私有快照稳定/异常0/lease0/DMA与timer/GIC证明/实际TTY与listen仍4096B →
与RPMsg计数交叉匹配 → rm临时client → 重绑Linux并确认两端100Full/ANon → 管理/工控/micad/boot不变 → 去hold → 最后复核。

拒绝并发额外实例，不只是统计两个Offline；启动前发生insmod不确定、启动/命令/私有证明失败时保留资源。
未知状态不CPU_OFF、不rm/rebind/rmmod、不自动重启/重试；停止命令失败或停核后证明失败也不第二次停止。
即使回包超时后只观察到完成并安全归还，首次错误仍记为FAIL，不伪装首次成功。
`board-result.json`只创建不覆盖，即使资源保留也记录失败；不能通过删除单次标记自行重复。
普通Python异常或主体阶段的用户中断会尝试保守收尾；收尾再次中断/强制杀进程/断电仍可能无结果文件，单次标记保留且禁止自动重试。

## 软件验证

[首次 ABI/测试日志](abi-native-first.log)：ABI已经通过，但新构建服务器目录漏传既有正式UP1 ELF，使一项旧MMU测试报缺文件；未接触板卡。
补齐正式两ELF输入后，[完整 ABI/168 Python/旧全套原生](abi-native-final.log)通过。
最后少量runner收尾完善后，[最终 Linux 检查](linux-final-v3.log)、[Windows168项](windows-tests.log)及[最终 ABI](nmt-abi-final-v3.json)通过。
期间两次构建服务器SSH在banner阶段EOF，尚未认证/上传或执行远端命令；只读socket随后读到OpenSSH9.6，第三次连接恢复并完成上述最终检查。
真实旧NMT栈25+邮箱4、P3f/P3e/P3d/P3c/P3b、累计parser/18lifecycle/3codec回归通过，硬件边界mock。
本轮没有 sanitizer、实机时延/堆峰值、真实 NMT/MN/CN 验收。未增加固件栈或改变既有320B状态输入帧。

## 换机与将来的板端步骤

先按[完整P3g构建/复编入口](../powerlink-nmt-p3g-20261023/README.md)恢复完整源码、固定SDK/工具链和摘要Docker。
进入stage07，在Linux构建机执行：

```bash
python3 tests/audit_powerlink_nmt_abi.py tests/powerlink-nmt-p3g-20261023/candidates/tl3572-m7-powerlink-p3g-up-b.elf \
  /home/openeuler/build/tl3572-2oo3/toolchain-14.3 /path/to/new-nmt-abi.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
POWERLINK_BUILD_ROOT=/path/to/verified-p3g-software bash tests/run_powerlink_nmt_probe_native.sh
```

**获新的明确许可后**，将板端依赖放入独立 `/root/m7-powerlink-nmt-p3g-20261023`，候选和
`up-b-m7-plk-nmt-probe.conf`放同一根。复制所有`tests/board/*.py`、`tests/*.py`到脚本可导入目录；
共享日志reader继续用固定 `/usr/libexec/m7/up_log_reader.py`（源码已归档），不修改开机服务。
host hold继续匹配 `/root/m7-eth-direct-20261010/m7_eth2_power_hold.ko`、SHA b071d434...，正式kernel6.12.69-gf1b67c293213。
清单显式含该KO、源码、Makefile及完整构建脚本；不以旧外部目录替代源码交付。

仅授权窗口内运行：

```bash
python3 run_powerlink_nmt_probe.py --confirm-isolated-bounded-nmt-reset \
  --sha256 85e78eb4bb150633e695014b5ecc55401a048a2707175a031b97a2e00567f68e
```

这是脚本门槛，不是自动获得人的许可。reset不是板卡reboot，也不是只读；可能产生有限协议帧，必须隔离。
不启动持续MN、不发送专用测试/CAN/串口帧、不接真实CN/伺服、不改正式固件/DT/开机配置、不自动重启。
停止不明时保留资源并另行处理，禁止套用历史固定故障恢复脚本。

构建服务器准备根 `/home/openeuler/build/powerlink-nmt-p3g-runner-20261023`，不是板卡测试根的实际存在证明。
本轮清单/后验GitHub拉取验证和`delivery/`按最终报告为准；旧清单到历史commit验证。

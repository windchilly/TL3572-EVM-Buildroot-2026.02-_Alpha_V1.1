# P3b：累计 UP2 的休眠 POWERLINK owner / 完整 ELF 链接

2026-10-10 完成软件检查点，**不是整个 P3、主站运行或实机验收**。
UP2仍为MN目标；本轮没有连接板卡/COM7、改PHY/DT/时钟、绑定/解绑、重启、部署或发送。
CAN/RS-232/RS-485接线已改变后的“先不要发送”继续有效。

## 已实现

- 新`rk3572_powerlink_app.c/h`：仅CPU5创建1个owner，32KiB对齐静态栈，优先级24。
  默认只休眠，不调用oplk_initialize或硬件prepare；2tick轮询不是POWERLINK周期性能承诺。
- 单槽邮箱只接受一个pending或running请求；拒绝busy/wrong-state/not-ready，序号不回绕。
  RPMsg仅投递软件命令/读缓存，不代理GMAC收发。实际协议调用由同一owner执行。
- IRQ锁只保护claim/copy/publish，不包围栈API、打印、RPMsg发送或Delay。
  owner/ISR/IRQ检查异常或Delay失败终止软件入口并保留诊断/资源，不重试或未知清理。
- `PLK status`跨任务读快照；`PLK env-init`调用真实软件环境初始化，`PLK env-exit`退出环境。
  默认COLD；初始化后IDLE，退出回COLD。无prepare/process/reset/start/send命令。
  非法、截断、嵌入NUL、超过48B记录拒绝；允许一组LF/CRLF。UP1明确拒绝PLK命令。
- 累计CAN经典/FD、232、485、旧ETH测试及M6普通RPMsg echo保留；本轮只做软件回归。
- 新0013默认OFF；UP2最终链接P3a完整对象一次，移除重复port对象，明确no-gc。
  全部596个核心/OD/port/BSP全局函数保留，RTOS及libc依赖全部解析，不再把可重定位文件当最终ELF。

## 软件证据与边界

12组真实完整栈owner原生场景通过：默认100次休眠、100次env初始化/退出、pending/running忙保护、
跨任务缓存/非owner拒绝、非法长度/NUL/禁用命令、create/resume/delete故障、ISR/IRQmasked、
环境已建立后的Delay异常资源保留、真实栈初始化失败、累计init/路由及第5任务失败清理。
另测UP1拒绝；只mockRTOS/硬件边界，未fake MN生命周期，硬件acquire/TX始终零。
P0/P1/P2/P3a原生NMT/OD、EDRV9组、RTOS12组、完整栈25组回归通过。
原累计parser/18调度生命周期/3codec回归通过；Windows/Linux各92项Python通过。

两个独立软件根、两个全新累计源码根，9个库/合并对象及2个runtime bin逐字节一致，
详见[repro-report.json](repro-report.json)。含路径的ELF调试信息不要求跨目录相同。
[owner-audit.json](owner-audit.json)与[复编审计](owner-repro-audit.json)记录最终链接与实际页表。

| 候选 | runtime字节 | image含NOLOAD/BSS字节 | 私有预留 | 页表 |
|---|---:|---:|---:|---:|
| UP1 | 360716 | 969056 | 8MiB | 9/16 |
| UP2 | 610900 | 2136096 | 8MiB | 10/16 |

UP1只增加PLK拒绝路由，不链接主站；因此runtime与旧正式UP1不同。
FSC池保持512KiB，静态owner栈不取FSC；上述是静态空间检查，不是实机堆余量、栈峰值或实时验收。
UP2 runtime SHA256 `59ce0994a824f47c138b77029a5b776388b35e70ad5209a5e7fdf2d3924e1365`。
原M6/endian/RWX及上游告警完整保留，未声称零告警；环境仍无ASan/UBSan运行库。

最终ELF全量审计首次暴露原M6/libmetal既有FP/SIMD：125条、10个函数（包括浮点格式化/metal_io_init）。
新增核心和适配保持general-registers-only、无FP/SIMD。审计将候选每个FP/SIMD位点与固定正式UP2对比；
仅两处PRT_cvt的LDR literal地址因链接重定位改变，另外核对相同寄存器与实际常量字节。
**整个ELF并非无FPU**，旧上下文行为仍须在后续板端/生产验证中确认；没有借此改动M6静态库。
负面回归验证新增函数/偏移/指令/常量变化会拒绝，不使用全局忽略SIMD。

## 保存位置与完整记录

构建Docker：`dev_openeuler`，容器工作根：
`/home/openeuler/build/powerlink-mn-p3b-20261010`。

- `software-checked-final` / `software-checked-repro`：两份全新P3a/P0/P1/P2软件根。
- `UniProton-verified-final` / `UniProton-verified-repro`：当前最终两份全新M6+累计+0011/12/13候选根。
- `delivery`：本轮SHA256SUMS精确列出的源码/脚本/证据/正式与候选ELF镜像，供归类恢复。
- [verified-final.log](verified-final.log)、[verified-repro.log](verified-repro.log)：最终完整候选构建与真实owner测试。
- [checked-final.log](checked-final.log)、[checked-repro.log](checked-repro.log)：全新P3a依赖链完整构建/原生回归。
- [validation-final-v3.log](validation-final-v3.log)：修正故障断言后的两根native、原回归、92Python和初次比对。
- [repro-validation.log](repro-validation.log)：最终候选根的11产物比对和审计。
- 其余first/checked/final/v2/simd日志保留：包含patch hunk计数错误、UP1不该include MN头、
  全ELF审计发现既有SIMD、PRT_cvt literal重定位诊断，以及mock消费任务非owner导致的测试断言修正。
  这些失败不隐去；它们没有在板卡上执行。

本目录`candidates/`两ELF用Git LFS单独归档，供后续受控板端测试；**不得自动安装**。
正式`firmware/tl3572-m7-integrated-up-a/b.elf`未替换，SHA仍为`8bfb824b...`/`627545f5...`，M6/DT不变。
`SHA256SUMS`校验当前源码/脚本/证据/候选；旧阶段清单要在该阶段历史提交检查，不套用到增量HEAD。

## 换机复建（固定构建环境）

先按仓库[RK3572空目录复建](../../../../repro-inputs/rk3572/README.md)恢复固定M6完整源码、
SDK/Arm14.3工具链及UniProton静态库；按原方案联网下载固定摘要Docker，不提交镜像层。
不能拿Windows直接替代Linux/AArch64构建环境。

```sh
export TL3572_PROJECT=/home/openeuler/build/tl3572-2oo3
export TOOLCHAIN_PATH="$TL3572_PROJECT/toolchain-14.3"
export M6_UNIPROTON_ROOT="$TL3572_PROJECT/src/UniProton"
stage=/absolute/github/clone/stages/stage07-peripheral-partition
work=/home/openeuler/build/powerlink-p3b-new-machine
# work/software 与 work/UniProton 必须不存在；脚本拒绝覆盖。
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/build/build_m7_powerlink_passive_mn.sh"
POWERLINK_BUILD_ROOT="$work/software" UNIPROTON_ROOT="$work/UniProton" \
    bash "$stage/build/build_m7_powerlink_owner_candidate.sh"
POWERLINK_BUILD_ROOT="$work/software" bash "$stage/tests/run_powerlink_owner_native.sh"
bash "$stage/tests/run_integrated_native.sh"
python3 -m unittest discover -s "$stage/tests" -p 'test_*.py' -v
```

最终ELF/bin/map/audit位于`work/UniProton/demos/rk3572_mica/build/`。
重复到另一组全新根，然后运行`tests/compare_powerlink_p3b.py software1 software2 UniProton1 UniProton2 report.json`。
源码归档、锁定上游、0001–0005、完整OD和0011/12/13、真实BSP/任务/测试/脚本均在本轮清单中；
不增加其它阶段完整源码归档的重复大包。

下一步：受控timer-only CNTP/PPI30权限/IRQ/延迟；然后forced100-half PHY/MAC与安全停止。
全部门槛通过才开放MN reset/start，再接隔离CN做PDO/SDO、失链/恢复/负载互操作。
当前不能控制真实CN/伺服，无周期/轴数/节点容量保证。

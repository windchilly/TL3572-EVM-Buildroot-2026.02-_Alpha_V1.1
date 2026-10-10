# UP2 / ETH2 POWERLINK MN 移植入口

用户已确认 UP2 做 Managing Node（MN，主站），控制外部设备。当前入口是
**P3b累计候选接入：完整核心/OD/port/真实BSP + 休眠owner/单槽邮箱/诊断快照**，
不是已能上网运行的主站；半双工上板仍待验证。

上游完整源码归档（包括文档、工具和示例）存放于 `upstream/`，采用 Git LFS。
以 `upstream.lock.json` 的提交、SHA256 和源码树为准，不在构建时跟随 master。
上游许可证及各文件版权声明保留在归档内；本适配代码不引入 Linux 网卡驱动。

`port/` 使用同一进程内的 user/kernel 逻辑层，复用上游 direct/local/no-OS CAL，
不要求 Linux 内核，也不使用 UP1/openEuler 作为实时数据代理。
这里的静态库故意不提供 EDRV、hrestimer、target 的硬件实现；它不能独立链接成可运行主站。
不允许用返回成功的空实现来掩盖未实现的硬件依赖。

上述是 `port/CMakeLists.txt` 的 P0 核心边界，保留其构建/审计不变。
P1 单独入口 `port/edrv/CMakeLists.txt` 实现 9 个 EDRV 接口；BSP 编译开关默认为 OFF，
只在累计 UP2 候选中启用，没有运行入口。TX 独立缓冲池、组播/软件过滤、FCS 处理和
安全停止的实际范围、串行 owner 约束及证据见 [P1 记录](../../tests/powerlink-mn-p1-20261010/README.md)。

P2 新入口 `port/rtos/CMakeLists.txt`，实现其余 target/cache/hrestimer 接口；
真实平台只在默认 OFF 的 `M7_POWERLINK_RTOS` 累计 UP2 候选开关中编译。
CNTP/PPI30 独占，原 CNTV/PPI27 Tick 不动；ISR 只屏蔽/计数，协议回调由同一 UP2 owner 任务泵送。
上述P2轮次没有RTOS常驻owner任务；最新P3b已补休眠任务，但仍无MN运行命令、半双工实机或定时精度结论。
资源与 RTOS 私有 ABI 限制、12 组原生测试及完整换机步骤见 [P2 记录](../../tests/powerlink-mn-p2-20261010/README.md)。

P3a入口`port/mn/CMakeLists.txt`，在另一份解包源码应用0003/0004/0005，
统一核心/OD配置并补安全停止/错误传播；部分初始化失败保留终止FAULT，不隐式回滚。
真实栈100次被动启停、16分配位置故障注入通过；仍无RTOS常驻任务/命令/最终MN ELF。
详见[P3a记录](../../tests/powerlink-mn-p3a-20261010/README.md)。

P3b通过`build_m7_powerlink_owner_candidate.sh`应用0013，完整P3a对象只链接一次，
明确禁止gc掉未开放的MN/OD代码；最终596个全局函数存在、RTOS/libc依赖全部解析。
新`rk3572_powerlink_app.c/h`与累计调度器接入，仅UP2创建32KiB静态栈owner，默认休眠。
`PLK status`读取IRQ锁保护缓存；`PLK env-init/env-exit`只投递单槽命令，owner执行软件环境生命周期。
没有prepare/process/reset/start/send命令，2tick休眠轮询不是POWERLINK周期或实时性能承诺。
部分失败/非法上下文/Delay异常保留诊断且拒绝后续命令，不释放未知资源或自动重启。
完整源代码、独立候选两ELF、12组C/92项Python及双目录11产物比对见[P3b记录](../../tests/powerlink-mn-p3b-20261010/README.md)。
新增核心/适配无FP/SIMD；原M6/libmetal既有125条仍保留，审计逐点比对，不能称整个最终ELF无FPU。

P0配置不使用Socket/UDP、虚拟网卡、文件配置或主站冗余；P3a CDC由静态内存提供。
保持整数对象范围检查；REAL32/REAL64 的**范围检查**显式拒绝（`kErrorObdUnknownObjectType`），
以匹配现有累计固件的 general-registers-only 编译约束，不偷偷启用浮点上下文。
没有范围属性的浮点对象仍可作为原始字节搬运；不表示 UP2 支持浮点计算。
老上游的 fallthrough/array-bounds 编译告警保留在构建日志，不作为零告警或生产认证通过。

P0 之后仍需依次实现和验证：

1. ETH2 通用 EDRV：持续运行、DMA 生命周期、组播、及时收包、发送完成及安全停止。
2. UniProton target/内存/临界区及 MN 高精度定时、周期发帧调度。
3. MAC/PHY 100M 半双工验证；固定资源移交。当前 100M 全双工测试不能代替。
4. 累计 UP2 固件内的 MN 任务、对象字典、节点配置、PDO/SDO、状态与日志。
5. 隔离 CN 对端上的互操作、周期抖动/最坏响应、负载、失链恢复和组合回归。

参考：[上游移植指南](https://github.com/OpenAutomationTechnologies/openPOWERLINK_V2/blob/V2.7.2/doc/porting-guide.md)、
[POWERLINK DS301，第3章](https://www.br-automation.com/downloads_br_productcatalogue/assets/EPSG_301_V-1-5-1_DS-c710608e.pdf)。

当前不修改正式累计 ELF，不部署板卡，不改变 CAN/UART 接线或发送状态。

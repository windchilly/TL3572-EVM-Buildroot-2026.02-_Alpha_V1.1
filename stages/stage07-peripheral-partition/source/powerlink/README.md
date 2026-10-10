# UP2 / ETH2 POWERLINK MN 移植入口

用户已确认 UP2 做 Managing Node（MN，主站），控制外部设备。当前入口是
**P0：完整源码固定 + AArch64 可移植核心构建 + 无硬件单元验证**，不是已能上网运行的主站。

上游完整源码归档（包括文档、工具和示例）存放于 `upstream/`，采用 Git LFS。
以 `upstream.lock.json` 的提交、SHA256 和源码树为准，不在构建时跟随 master。
上游许可证及各文件版权声明保留在归档内；本适配代码不引入 Linux 网卡驱动。

`port/` 使用同一进程内的 user/kernel 逻辑层，复用上游 direct/local/no-OS CAL，
不要求 Linux 内核，也不使用 UP1/openEuler 作为实时数据代理。
这里的静态库故意不提供 EDRV、hrestimer、target 的硬件实现；它不能独立链接成可运行主站。
不允许用返回成功的空实现来掩盖未实现的硬件依赖。

P0 配置不使用 Socket/UDP、虚拟网卡、文件配置或主站冗余，CDC 配置须以后由内存提供。
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

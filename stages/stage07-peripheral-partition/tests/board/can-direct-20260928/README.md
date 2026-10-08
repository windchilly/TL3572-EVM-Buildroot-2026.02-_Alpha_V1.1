# UP1 / UP2 经典 CAN 寄存器直驱测试（2026-09-28）

结论：UP1/CAN FD1 与 UP2/CAN FD3 的经典 CAN 数据路径 **PASS**。Linux 在测试窗口内已解绑 CAN1、CAN3；UP1、UP2 分别直接初始化和轮询 `0x2ab10000`、`0x2ab30000` 控制器，完成三轮各 1,000 次请求/应答，双方每轮均为 TX=1,000、RX=1,000、TXERR=0、RXERR=0。

## 测试边界

- UP1 / CPU4：板载 CAN FD1、CAN1、MMIO `0x2ab10000`，发送 ID `0x321` 请求。
- UP2 / CPU5：板载 CAN FD3、CAN3、MMIO `0x2ab30000`，接收请求并以 ID `0x456` 响应。
- 固定 8 字节经典 CAN 帧，1 Mbit/s 名义速率；297 MHz 时钟下 NBTP=`0x1200256d`，与已验证的 Linux 实机参数一致。
- 驱动采用轮询，不依赖 Linux SocketCAN、RPMsg 数据代理或 CAN IRQ；RPMsg 只保留为 MICA 管理/诊断通道。
- Linux 先使能既有 pinctrl/clock，并把控制器置于 clean reset 状态，随后 sysfs unbind；UP 固件尚未自己编程 CRU、reset 和 pinctrl。因此本结果证明的是 **UP 数据面寄存器直驱**，还不是从上电开始完全脱离 Linux 的最终资源移交。
- 本轮未实现 CAN FD 64 字节帧、数据相位/BRS、中断模式，也未测试 FD2/FD4。

## 结果

| 轮次 | UP1 | UP2 | 清理 |
|---|---|---|---|
| 修复后第 1 轮 / boot 137 | TX/RX 1000/1000，错误 0 | TX/RX 1000/1000，错误 0 | PASS |
| 修复后第 2 轮 / boot 138 | TX/RX 1000/1000，错误 0 | TX/RX 1000/1000，错误 0 | PASS |
| 修复后第 3 轮 / boot 139 | TX/RX 1000/1000，错误 0 | TX/RX 1000/1000，错误 0 | PASS |

三轮合计 3,000 次请求和 3,000 次响应；每个 UP 合计发送 3,000 帧、接收 3,000 帧。每轮均完整执行 Linux unbind → UP2 启动 → UP1 启动 → 互发 → 双 UP 停止/删除 → Linux rebind。

2026-10-08 将板端执行器加固为：临时实例停止/删除后通过 MCS PSCI 查询分别确认 CPU4、CPU5 已 OFF，再允许 Linux rebind。使用相同哈希的两份 ELF 又完成一轮 1,000 次请求/应答，双方 TX/RX=1000/1000、TXERR/RXERR=0，CPU4/5 OFF 确认和两路 rebind 均通过。至此累计四轮、4,000 次请求和 4,000 次响应；每个 UP 累计 TX/RX 各 4,000 帧。此次板卡的 `micad` PID 为 320，`NRestarts=0`；原实例 `up-a/up-b` 均 Offline，`can1/can3` 为 DOWN。见 `can-direct-run-20261008-v5.log`。

首轮开发测试保留为 `can-direct-run-20260928.log`：UP1 首帧已被 UP2 收到，说明物理直驱数据已到达；但测试代码将 `CAN_INT_MASK` 写成 `0xffffffff`，发送完成状态不可见，两端误判超时。改为与厂商驱动运行值一致的 `0x1` 后，连续三轮通过。该失败不是接线或总线故障。

最终状态：临时 `up-a-m7-can`、`up-b-m7-can` 已停止并删除，原 `up-a/up-b` 均 Offline；CAN1、CAN3 已重新绑定 `rk3576_can` 且保持 DOWN；`micad` 保持 PID 4028、`NRestarts=0`、active。没有刷写 boot 镜像或修改开机配置。

## 复现入口

构建环境中准备 M7 源码后执行：

```sh
bash stages/stage07-peripheral-partition/build/prepare_m7_uniproton.sh
bash stages/stage07-peripheral-partition/build/build_m7_can_direct_test.sh
```

生成：

- `tl3572-m7-can-up-a.elf`：SHA-256 `1c74d021f04547a2aca707e4ff6495716b30110c47ba2038e12cda47684e7ed0`
- `tl3572-m7-can-up-b.elf`：SHA-256 `cdcd67e954326d79ae69704495cb1abed7a7f697a6acc108378e21f54c8770b6`

把 ELF 与 [`up-a-m7-can.conf`](../up-a-m7-can.conf)、[`up-b-m7-can.conf`](../up-b-m7-can.conf) 按配置中的路径放入板卡，只在 FD1-H↔FD3-H、FD1-L↔FD3-L、GND↔GND 且端接正确时，以 root 执行：

```sh
python3 run_can_direct_pair.py
```

[`run_can_direct_pair.py`](../run_can_direct_pair.py) 会核对控制器映射和原实例状态、初始化再解绑 Linux 控制器、按 UP2→UP1 顺序启动、只读取本轮新增保留内存日志，并在 `finally` 中停止临时实例、确认 CPU4/5 PSCI OFF、重绑控制器和核对 `micad`。若 CPU OFF 无法确认，执行器保留 Linux 控制器解绑状态并报错，避免双重占用；应停止自动重试并人工诊断。测试失败也必须检查其最终回收结果，不能只读 Python 退出码。

## 证据

- `can-direct-build-final.log`：最终两份 ELF 的增量重建与哈希。
- `can-direct-run-20260928.log`：首轮状态屏蔽缺陷及安全回收。
- `can-direct-run-20260928-v2.log` 至 `v4.log`：三轮通过记录。
- `can-direct-run-20261008-v5.log`：加固回收门槛后的第四轮通过记录。
- `can-direct-final-state-20260928.log`：最终服务、实例、驱动绑定和 CAN 错误统计。
- `SHA256SUMS`：上述原始日志校验值。

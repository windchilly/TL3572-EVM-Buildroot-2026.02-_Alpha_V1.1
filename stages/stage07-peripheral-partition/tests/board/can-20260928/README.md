# CAN FD1 ↔ CAN FD3 物理基线测试（2026-09-28）

结论：经典 CAN 双向物理链路 **PASS**；CAN FD/BRS 被当前 Linux 驱动能力阻塞；UniProton 直驱尚未开始，不能把本记录作为 UP1/UP2 外设移交验收。

## 接线与映射

断电接线为 FD1-H ↔ FD3-H、FD1-L ↔ FD3-L、GND ↔ GND，J9、J13 接入两端 120 Ω 终端。测试前确认总线 H-L 约 60 Ω，未将 CAN-H 与 CAN-L 短接。

| 物理接口 | Linux 接口 | 控制器 | GIC SPI | M7.0 目标所有者 |
|---|---|---|---:|---|
| CAN FD1 | `can1` | `0x2ab10000` / CAN1 | 153 | UP1 |
| CAN FD3 | `can3` | `0x2ab30000` / CAN3 | 155 | UP2 |

本轮仍由 openEuler 的 `rk3576_can` 驱动两个控制器，只验证板端控制器、收发器、端接和接线构成的物理基线。它不验证 Linux 已释放资源，也不验证 UniProton 能访问控制器寄存器、中断和时钟。

## 方法与结果

使用 [`../can_physical_pair_test.py`](../can_physical_pair_test.py) 为两个 Linux 接口分别建立 CAN RAW socket，逐帧发送带方向标识和序号的负载，并在另一个物理接口核对 ID 与完整数据。没有使用同接口软件回环。

板卡上的经典 CAN 冒烟可按下列命令复现（只连接隔离测试对端，不连接执行器）：

```sh
ip link set can1 down
ip link set can3 down
ip link set can1 type can bitrate 1000000 restart-ms 100
ip link set can3 type can bitrate 1000000 restart-ms 100
ip link set can1 up
ip link set can3 up
python3 can_physical_pair_test.py can1 can3 --count 256
ip -details -statistics link show can1
ip -details -statistics link show can3
ip link set can1 down
ip link set can3 down
```

- 标称仲裁速率：1 Mbit/s；297 MHz 控制器时钟下实际为 996,644 bit/s，采样点 0.744；两端参数一致。
- 冒烟：每方向 256/256 帧通过。
- 压力：每方向 10,000/10,000 帧通过。
- 恢复：接口 stop/start 三轮，每轮每方向 128/128 帧通过。
- 每个接口累计 RX/TX 均为 10,640 帧、85,120 字节。
- 两端最终均为 `ERROR-ACTIVE`，berr-counter、重启、总线错误、仲裁丢失、warning、error-passive、bus-off、RX/TX error/drop 均为 0。
- 测试结束后 `can1`、`can3` 已恢复 DOWN；UP1/UP2 保持 Offline，`micad` 保持 active。

## CAN FD 阻塞项

配置 `fd on` 返回 `RTNETLINK answers: Operation not supported`，切换 MTU 72 返回 `Invalid argument`，接口保持 MTU 16。源码 `drivers/net/can/rockchip/rk3576_can.c` 虽定义数据位时序和 64 字节寄存器区，但只声明 `CAN_CTRLMODE_LOOPBACK | CAN_CTRLMODE_LISTENONLY`，发送路径使用 `struct can_frame`，未向 SocketCAN 注册 FD/BRS 能力。

因此这里只能得出“当前 Linux 驱动未实现 CAN FD”，不能得出 RK3572 控制器或板载 TCAN1057A 不支持 CAN FD。现有 UniProton RK3572 BSP 中也未找到 CAN 驱动。

## M7.0 后续门槛

1. 在 Linux 设备树中分别释放 CAN1 给 UP1、CAN3 给 UP2，并成套处理 pinctrl、clock/reset、IRQ 及共享资源。
2. 为 UniProton 实现 RK3572 CAN 控制器初始化、中断、错误状态和经典 CAN 收发，先复现本记录的双向、压力和单边重启测试。
3. 补齐 FD 数据位时序、64 字节帧和 BRS 后，再执行 CAN FD 专项压力与故障恢复；FD1/FD2、FD3/FD4 四口映射逐口实测。

## 原始证据

- `can-classic-20260928.log`：256 帧/方向冒烟。
- `can-classic-stress-20260928.log`：10,000 帧/方向压力。
- `can-classic-restart-20260928.log`：三轮 stop/start。
- `can-final-state-20260928.log`：累计计数及错误统计。
- `can-fd-capability-20260928.log`：FD 配置失败和接口能力。
- `can-platform-state-20260928.log`：UP 状态及 `micad` 状态。
- `can-kernel-20260928.log`：相关内核日志。
- `SHA256SUMS`：上述原始文件校验值。

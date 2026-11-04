# P3j：一次有界周期实测窗口（2026-11-04）

状态：准备只读预检；尚未执行，不是 PASS。

用户新确认：“隔离回环仍在，允许一次 P3j 有界周期测试”。
仅固定候选 `4b4854157487a8ddfa07914c01efbe6c7215c1eed273f9e80e405f6b9c3d9c35`，
临时移交 ETH2/CNTP，单次 reset→Operational（100ms 或256次TX完成先到，总软件预算8s）→排空→SwitchOff。
只在停止及真实堆证明完整后归还Linux；可能发有限POWERLINK协议帧。
不含持续运行、真实CN/执行器、CAN/串口、专用测试帧、正式固件/开机修改、自动重启或异常重试。
隔离ETH2↔ETH3不改变，不打开COM7。未知状态保留现场。

主机编排源码为本目录 `board_window.py`；实际runner/19项输入见
[固定软件准备](../powerlink-cycle-p3j-runner-20261104/README.md)。
预检和回执/原始结果会分别保留，测试结束后更新结论；不得覆盖或删除ATTEMPTED来重投。

# 厂商软件输入与参考产物

本目录是 TL3572 厂商软件资料，不替代 [全阶段 openEuler / UniProton 构建入口](../repro-inputs/all-stages/README.md)。

| 分类 | 内容 |
|---|---|
| [sources/kernel/](sources/kernel/) | 原厂完整 Linux 6.12.69 源码包 |
| [sources/u-boot/](sources/u-boot/) | 原厂完整 U-Boot 2025.04 源码包 |
| [sources/buildroot/](sources/buildroot/) | 原厂完整 Buildroot 2026.02 源码包 |
| [toolchains/](toolchains/) | 固定 Arm GNU 14.3 交叉工具链；prepare 脚本验证固定 SHA256 |
| [examples/](examples/) | 基础 CAN/串口/GPIO 示例、4G/5G/Wi-Fi 资料、音频/PLP/Qt 示例 |
| [firmware/kernel/](firmware/kernel/) | 厂商参考 boot.img，回滚和 DT/配置对照用 |
| [firmware/u-boot/](firmware/u-boot/) | 厂商 loader 与 uboot.img |
| [firmware/updateimg/](firmware/updateimg/) | 原厂整包更新镜像元数据；完整 update.img 仅本机保留 |

`firmware/rootfs/` 的完整 rootfs 与 update.img 是忽略的本机参考产物，并未删除；
从 GitHub 克隆不会带回这两份大型镜像。正式各 Stage 交付物仍在 `../stages/`。
示例目录含源码和原厂随附参考二进制，未把只有二进制的模块示例冒充完整源码。

Windows 板级工具已按刷机、驱动、工控调试、通信、诊断分类到
`.local-only/tools/windows/`（相对仓库根目录），不上传第三方安装程序。
原厂整体 SDK/dl/sysroot 保留在 `.local-only/vendor-sdk/`；说明见
[本机整体 SDK 归档](../docs/vendor-notes/sdk/LOCAL_ARCHIVE.md)。

# 本地整体 SDK 的新位置

整体 LinuxSDK、下载缓存和生成 sysroot 不参与本仓库的 openEuler Stage 复建，现分类保留在：

```text
.local-only/vendor-sdk/LinuxSDK-v1.0.tar.gz
.local-only/vendor-sdk/dl.tar.gz
.local-only/vendor-sdk/rk3572-buildroot-2026.02-sysroot-v1.0.tar.gz
```

它们没有删除，也没有上传 GitHub。原厂功能说明和 MD5 文件仍在当前目录；
如检查 MD5，需在新归档目录指定该清单路径，或先恢复归档至原位置。
实际使用的厂商 Buildroot、U-Boot、内核源包和 Arm 工具链保持原路径。

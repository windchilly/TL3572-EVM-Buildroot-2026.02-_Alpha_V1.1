# M6 双实例构建摘要

- 日期：2026-09-21
- 工作区：`/home/openeuler/build/tl3572-2oo3`
- 容器：`dev_openeuler`
- MACHINE：`tl3572-evm`
- 内核：`6.12.69-gf1b67c293213`
- 最终命令：`bash rebuild-m6-dual-image.sh`
- 清理范围：`linux-tl3572 -c clean`、`mcs-linux -c clean`
- 最终结果：`Attempted 2920 tasks ... all succeeded`
- 最终 warning：0
- `linux-tl3572:do_patch`：成功，无 fuzz
- boot SHA256：`a6a050cd9aa335516907ca79c290084e9585c03c3d53a660d262c8789515a436`
- mcs_km SHA256：`85818cc30f503f3fb84c548ebac2ebce76adb68d57d5e6fea63e74d0a1baff6c`
- micad SHA256：`d6722cc43f411c4fb3a00c257d82e3bef74819521f3587ae64e327e752aa6dae`

首次包含 GIC target-map 修复的构建也完成 2920/2920，但补丁因宽上下文出现
`fuzz 2`。随后将 GIC 改动拆为两个精确 hunk，再次从 clean 状态全量构建；最终
归档只保留无 fuzz、零 warning 的第二次产物。

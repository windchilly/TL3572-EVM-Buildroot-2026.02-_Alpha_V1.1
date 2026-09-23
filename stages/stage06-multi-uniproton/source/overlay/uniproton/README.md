# UniProton M6 覆盖文件

基线为 Stage05 已验证的 `/home/openeuler/build/tl3572-2oo3/src/UniProton/`。
本目录从 UniProton 仓库根开始保持相对路径不变：`demos/rk3572_mica/` 覆盖板级
demo，`src/component/mica/openamp_common.h` 覆盖全局 MICA 组件。覆盖后执行：

```bash
cd /home/openeuler/build/tl3572-2oo3/src/UniProton/demos/rk3572_mica/build
bash build_m6_instances.sh
```

脚本生成 `rk3572-uniproton-up-a.elf` 和 `rk3572-uniproton-up-b.elf`，并将 CPU、SGI、
镜像入口和 MMU 地址作为 CMake 参数传入。生成后必须与阶段根目录 `SHA256SUMS`
核对，不能混用 CPU5 前置阶段的单实例 ELF。

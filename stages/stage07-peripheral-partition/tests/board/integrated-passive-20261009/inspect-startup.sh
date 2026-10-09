set -eu
cd /home/openeuler/build/tl3572-2oo3/src/UniProton-m7-integrated-final-v2-20261009
sed -n '130,205p' demos/rk3572_mica/bsp/mmu.h
sed -n '1,240p' demos/rk3572_mica/bsp/mmu.c
sed -n '240,560p' demos/rk3572_mica/bsp/mmu.c
grep -R -n 'mmu_init\|CR_M\|g_mmu_page_end\|BSS\|bss' demos/rk3572_mica/bsp/start.S demos/rk3572_mica/bsp/rk3572/rk3572_mica.ld.in

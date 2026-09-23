import sys
p = "/home/openeuler/build/tl3572-2oo3/meta-tl3572-stage3/recipes-kernel/linux/linux-tl3572_6.12.69.bb"
s = open(p).read()
broken = 'grep -aq "vermagic=${TL3572_KO_VERMAGIC}" ${WORKDIR}/mcs-km/mcs_km.ko \\n        || bbfatal "mcs_km vermagic does not match ${TL3572_KO_VERMAGIC}"\n'
fixed = 'grep -aq "vermagic=${TL3572_KO_VERMAGIC}" ${WORKDIR}/mcs-km/mcs_km.ko || bbfatal "mcs_km vermagic does not match ${TL3572_KO_VERMAGIC}"\n'
assert broken in s, "broken line not found"
open(p, "w").write(s.replace(broken, fixed, 1))
print("VERMAGIC_LINE_FIXED")

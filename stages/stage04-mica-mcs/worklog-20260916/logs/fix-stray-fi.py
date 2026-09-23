import sys
p = "/home/openeuler/build/tl3572-2oo3/meta-tl3572-stage3/recipes-kernel/linux/linux-tl3572_6.12.69.bb"
s = open(p).read()
bad = '|| bbfatal "mcs_km vermagic does not match ${TL3572_KO_VERMAGIC}"\nfi\n'
good = '|| bbfatal "mcs_km vermagic does not match ${TL3572_KO_VERMAGIC}"\n'
assert s.count(bad) == 1, "expected exactly one stray-fi block, got %d" % s.count(bad)
open(p, 'w').write(s.replace(bad, good, 1))
print("STRAY_FI_REMOVED")

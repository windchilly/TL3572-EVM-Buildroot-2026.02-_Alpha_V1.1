# The generic openEuler QEMU seed installs a static 192.168.7.2 profile that
# matches every eth* interface.  TL3572 owns its network policy in
# 20-wired.network, so remove the earlier first-match profile at the package
# source instead of carrying two competing networkd configurations.
do_install:append() {
    rm -f ${D}${sysconfdir}/systemd/network/10-eth-static.network
}

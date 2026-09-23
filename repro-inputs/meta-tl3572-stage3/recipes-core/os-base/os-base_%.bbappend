do_install:append:tl3572-evm() {
    rm -f ${D}${sysconfdir}/systemd/network/10-eth-static.network
}


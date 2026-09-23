do_install:append:tl3572-evm() {
    ln -snf mica ${D}${bindir}/mcsctl
}

FILES:${PN}:append:tl3572-evm = " ${bindir}/mcsctl"


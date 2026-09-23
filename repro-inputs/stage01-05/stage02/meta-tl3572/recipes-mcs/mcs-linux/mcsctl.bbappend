# openEuler 24.03-LTS keeps the historical recipe/package name "mcsctl",
# while upstream micactl exposes only the console entry point "mica".
# Provide a compatibility command so scripts and validation procedures that
# use the package name can invoke the same official Python CLI.
do_install:append() {
    ln -snf mica ${D}${bindir}/mcsctl
}

FILES:${PN}:append = " ${bindir}/mcsctl"

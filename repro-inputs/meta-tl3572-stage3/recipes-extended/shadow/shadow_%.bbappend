# openEuler upgrades shadow to 4.14.3 while the kirkstone base recipe still
# carries its older native dependency behavior.  The resulting native
# configure enables xattr but does not stage attr headers in a fresh TMPDIR.
DEPENDS:append:class-native = " attr-native"


# The vendor kernel does not provide the audit capability required by auditd.
# Security audit is reconsidered with the phase-4 kernel configuration.
RDEPENDS:packagegroup-core-base-utils:remove:tl3572-evm = "audit auditd"


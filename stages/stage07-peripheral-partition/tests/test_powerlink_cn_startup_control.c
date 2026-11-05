/* Reuse immutable P4c module-mock regressions, explicitly mock the new bind.
 * early_kernel_cleanup now closes the gate on error; covered by the real-stack
 * P4e harness, not its older assertion that a failure leaves producers running. */
#include <common/m7_cn_startup.h>
#include "test_powerlink_cn_lifecycle.c"
tOplkError __wrap_m7_cn_edrv_activate(void)
{
    assert(m7_cn_activation_allowed() && !m7_cn_ready());return kErrorOk;
}

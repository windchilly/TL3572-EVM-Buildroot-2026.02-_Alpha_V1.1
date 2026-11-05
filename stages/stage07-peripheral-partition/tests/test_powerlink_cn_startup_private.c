/* Existing component tests deliberately isolate lifecycle from timer storage.
 * Full ready/stop gating is independently tested with all production modules. */
#include <common/m7_cn_startup.h>
#include "test_powerlink_cn_private.c"
int __wrap_m7_cn_wait_ready(void) { return !__wrap_m7_cn_stopping(); }
int __wrap_m7_cn_ready(void) { return !__wrap_m7_cn_stopping(); }

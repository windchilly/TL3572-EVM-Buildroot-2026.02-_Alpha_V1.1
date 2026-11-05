/* P4e Linux CN delivery gate. Not a frontend or execution authorization.
 * Commit only after full stack initialization and the one socket activation.
 * Stop/fault closes it; already admitted callbacks still require all joins. */
#ifndef M7_CN_STARTUP_H
#define M7_CN_STARTUP_H
#include <common/m7_cn_lifecycle.h>
int m7_cn_ready(void);
int m7_cn_wait_ready(void);
int m7_cn_activation_allowed(void);
tOplkError m7_cn_edrv_activate(void);
#endif

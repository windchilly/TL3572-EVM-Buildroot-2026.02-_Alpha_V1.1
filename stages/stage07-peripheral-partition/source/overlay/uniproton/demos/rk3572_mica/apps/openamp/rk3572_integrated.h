#ifndef RK3572_INTEGRATED_H
#define RK3572_INTEGRATED_H
#include "prt_typedef.h"
#include <stddef.h>
U32 Rk3572IntegratedInit(void);
int Rk3572IntegratedInput(const char *data, size_t length);
U32 Rk3572CanClassicTest(void);
U32 Rk3572CanFdTest(U32 profile);
U32 Rk3572Rs232Test(U32 baud);
U32 Rk3572Rs485Test(U32 baud);
#endif

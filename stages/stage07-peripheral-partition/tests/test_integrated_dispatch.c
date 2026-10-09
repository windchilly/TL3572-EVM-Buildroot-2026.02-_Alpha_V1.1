/* Native dispatcher tests with OS/driver stubs: no peripheral or board access. */
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "prt_task.h"
#include "rk3572_integrated.h"
static struct TskInitParam tasks[3];
static unsigned created, resumed, deleted, failCreate, failResume, calls[4], lastValue[3];
static char reply[200];
static jmp_buf workerExit;
uintptr_t PRT_HwiLock(void) { return 0U; }
void PRT_HwiRestore(uintptr_t lock) { (void)lock; }
int PRT_Printf(const char *format, ...) { (void)format; return 0; }
int send_message(unsigned char *message, int length)
{ assert(length > 0 && length < (int)sizeof(reply)); memcpy(reply, message, (size_t)length); reply[length] = 0; return length; }
U32 PRT_TaskCreate(TskHandle *task, struct TskInitParam *param)
{
    if (failCreate && created + 1U == failCreate) { return 101U; }
    assert(created < 3U && param->stackSize == 0x4000U && !(param->stackAddr & 15U));
    tasks[created] = *param; *task = created++; return 0U;
}
U32 PRT_TaskResume(TskHandle task) { assert(task < created); resumed++; return resumed == failResume ? 102U : 0U; }
U32 PRT_TaskDelete(TskHandle task) { assert(task < created); deleted++; return 0U; }
U32 PRT_TaskDelay(U32 ticks) { assert(ticks == 2U); longjmp(workerExit, 1); return 0U; }
U32 Rk3572CanClassicTest(void) { calls[0]++; lastValue[0] = 1U; return 0U; }
U32 Rk3572CanFdTest(U32 profile) { calls[1]++; lastValue[0] = profile; return 0U; }
U32 Rk3572Rs232Test(U32 baud) { calls[2]++; lastValue[1] = baud; return 0U; }
U32 Rk3572Rs485Test(U32 baud) { calls[3]++; lastValue[2] = baud; return 17U; }
static void input(const char *text, const char *expected)
{ assert(Rk3572IntegratedInput(text, strlen(text))); assert(strstr(reply, expected)); }
static void worker(unsigned index)
{
    if (!setjmp(workerExit)) { tasks[index].taskEntry(tasks[index].args[0], 0U, 0U, 0U); assert(0); }
}
int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "create")) { failCreate = (unsigned)atoi(argv[2]); }
    if (argc == 3 && !strcmp(argv[1], "resume")) { failResume = (unsigned)atoi(argv[2]); }
    input("M7 status", "ERROR not-ready");
    if (failCreate || failResume) {
        assert(Rk3572IntegratedInit() != 0U && deleted == created);
        input("M7 run all 115200 4", "ERROR not-ready");
        assert(!calls[0] && !calls[1] && !calls[2] && !calls[3]);
        puts("INTEGRATED INIT FAILURE PASS: all partial tasks deleted, no driver execution"); return 0;
    }
    assert(!Rk3572IntegratedInit() && !Rk3572IntegratedInit() && created == 3U && resumed == 3U);
    assert(!calls[0] && !calls[1] && !calls[2] && !calls[3]);
    input("M7 status", "pending=0x0 running=0x0 rc=0/0/0 done=0/0/0");
    assert(!Rk3572IntegratedInput("ordinary echo", 13U));
    input("M7 run can 3", "ERROR invalid-command");
    input("M7 run can 1", "ACCEPTED mask=0x1");
    input("M7 run can 4", "ERROR busy");
    input("M7 run all 115200 4", "ERROR busy");
    input("M7 status", "pending=0x1");
    worker(0); assert(calls[0] == 1U && calls[1] == 0U);
    input("M7 run all 38400 4", "ACCEPTED mask=0x7");
    input("M7 status", "pending=0x7");
    worker(0); worker(1); worker(2);
    assert(calls[1] == 1U && calls[2] == 1U && calls[3] == 1U);
    assert(lastValue[0] == 4U && lastValue[1] == 38400U && lastValue[2] == 38400U);
    input("M7 status", "pending=0x0 running=0x0 rc=0/0/17 done=2/1/1");
    input("M7 run rs232 9600", "ACCEPTED mask=0x2");
    worker(1); assert(calls[2] == 2U && lastValue[1] == 9600U);
    puts("INTEGRATED DISPATCH PASS: passive boot, classic/FD serialization, atomic group, independent workers, rerun, failure status");
    return 0;
}

/* Real P3a stack/ports + real P3b task/mailbox, only RTOS/hardware mocked.
 * Reuse the allocation/hardware mocks and regression functions, not fake MN. */
#define main P3aRegressionMain
#include "test_powerlink_passive_mn.c"
#undef main
#include <setjmp.h>
#include "prt_task.h"
#include "rk3572_powerlink_app.h"
#include "rk3572_integrated.h"
static struct TskInitParam ownerParam;
static unsigned created, resumed, deleted, failCreate, failResume, delayError, failDelete;
static TskHandle ownerId;
static unsigned locked;
static jmp_buf workerExit;
static char reply[400];
static int submittingDuringInit;
uintptr_t PRT_HwiLock(void) { ++locked; return m7_plk_irq_save(); }
void PRT_HwiRestore(uintptr_t state) {
    assert(locked); --locked; m7_plk_irq_restore(state);
    if (!locked && submittingDuringInit) {
        M7PowerlinkSnapshot out;
        submittingDuringInit = 0;
        assert(Rk3572PowerlinkSnapshot(&out) && out.running);
        assert(Rk3572PowerlinkInput("PLK env-exit", 12) && strstr(reply, "ERROR busy"));
    }
}
int PRT_Printf(const char* format, ...) { (void)format; return 0; }
int send_message(unsigned char* message, int length)
{ assert(!locked && length > 0 && length < (int)sizeof(reply)); memcpy(reply, message, (size_t)length); reply[length] = 0; return length; }
U32 PRT_TaskCreate(TskHandle* id, struct TskInitParam* param)
{
    ++created;
    if (created == failCreate) return 101;
    assert(!(param->stackAddr & 15U));
    if (!strcmp(param->name, "PLKowner")) {
        assert(param->stackSize == 0x8000 && param->taskPrio == 24);
        ownerParam = *param; ownerId = created + 2; *id = ownerId;
    } else {
        assert(created <= 4 && param->stackSize == 0x4000); *id = created - 1;
    }
    return 0;
}
U32 PRT_TaskResume(TskHandle id) { assert(id <= ownerId || id < 4); ++resumed; return resumed == failResume ? 102 : 0; }
U32 PRT_TaskDelete(TskHandle id) { (void)id; ++deleted; return failDelete ? 103 : 0; }
U32 Rk3572CanClassicTest(void) { assert(0); return 0; }
U32 Rk3572CanFdTest(U32 value) { (void)value; assert(0); return 0; }
U32 Rk3572Rs232Test(U32 value) { (void)value; assert(0); return 0; }
U32 Rk3572Rs485Test(U32 value) { (void)value; assert(0); return 0; }
U32 Rk3572EthTest(U32 value) { (void)value; assert(0); return 0; }
U32 PRT_TaskDelay(U32 ticks)
{ assert(ticks == 2 && !locked); if (delayError) return 104; longjmp(workerExit, 1); return 0; }
static M7PowerlinkSnapshot app_status(void)
{ M7PowerlinkSnapshot out; assert(Rk3572PowerlinkSnapshot(&out)); return out; }
static void input(const char* text, const char* expected)
{ assert(Rk3572PowerlinkInput(text, strlen(text))); assert(strstr(reply, expected)); }
static void step(void)
{
    task = ownerId;
    if (!setjmp(workerExit)) {
        ownerParam.taskEntry(0,0,0,0); assert(delayError || !app_status().ready);
    }
    task = 1;
}
static void dormant(void)
{
    unsigned i;
    assert(!Rk3572PowerlinkSnapshot(NULL));
    input("PLK env-init", "ERROR not-ready");
    input("PLK status", "state=0");
    assert(!Rk3572PowerlinkInit() && !Rk3572PowerlinkInit() && created == 1 && resumed == 1);
    for (i = 0; i < 100; ++i) step();
    assert(!m7_plk_owner() && !allocations && !timerAcquires && !ethAcquires && !sems);
    assert(app_status().owner == 3 && app_status().mn.owner == 0);
    input("PLK env-exit", "ERROR wrong-state");
    for (i = 0; i < 100; ++i) {
        input("PLK env-init\r\n", "ACCEPTED seq=");
        input("PLK env-exit", "ERROR busy");
        input("PLK status", "pending=1 running=0");
        submittingDuringInit = 1;
        step(); assert(!submittingDuringInit && app_status().mn.state == M7_MN_IDLE && app_status().mn.owner == 3);
        assert(app_status().completed == app_status().submitted);
        assert(m7_mn_initialize() != 0 && m7_mn_status(&(M7MnStatus){0}) != 0); /* consumer is not owner */
        input("PLK env-init", "ERROR wrong-state");
        input("PLK env-exit", "ACCEPTED seq="); step();
        assert(app_status().mn.state == M7_MN_COLD && !m7_plk_owner());
    }
    assert(app_status().completed == 200 && !allocations && !frees && !writes && !ethAcquires && !timerAcquires && !sems);
    input("PLK status", "done=200");
    assert(!Rk3572PowerlinkInput(NULL, 0));
    assert(!Rk3572PowerlinkInput("ordinary echo", 13));
    for (i = 4; i < strlen("PLK env-init"); ++i) {
        assert(Rk3572PowerlinkInput("PLK env-init", i)); assert(strstr(reply, "invalid-command"));
    }
    assert(Rk3572PowerlinkInput("PLK env-init\0x", 14)); assert(strstr(reply, "invalid-command"));
    input("PLK prepare", "ERROR invalid-command"); input("PLK start", "ERROR invalid-command");
    input("PLK timer-probe", "ERROR invalid-command"); input("PLK timer-status", "ERROR invalid-command");
    input("PLK reset", "ERROR invalid-command"); input("PLK env-init\n\n", "ERROR invalid-command");
    { char big[100]; memset(big, 'x', sizeof(big)); memcpy(big, "PLK ", 4);
      assert(Rk3572PowerlinkInput(big, sizeof(big)) && strstr(reply, "invalid-command")); }
}
#ifndef M7_OWNER_TEST_MAIN
#define M7_OWNER_TEST_MAIN main
#endif
int M7_OWNER_TEST_MAIN(int argc, char** argv)
{
    assert(argc == 2); (void)submittingDuringInit;
    if (!strcmp(argv[1], "integrated")) {
        assert(!Rk3572IntegratedInit() && !Rk3572IntegratedInit() && created == 5 && resumed == 5);
        assert(Rk3572IntegratedInput("PLK status", 10) && strstr(reply, "mode=software-only"));
        assert(Rk3572IntegratedInput("M7 status", 9) && strstr(reply, "ready=1"));
        assert(Rk3572IntegratedInput("PLK env-init", 12) && strstr(reply, "ACCEPTED"));
        step(); assert(app_status().mn.state == M7_MN_IDLE);
        assert(Rk3572IntegratedInput("PLK env-exit", 12) && strstr(reply, "ACCEPTED"));
        step(); assert(app_status().mn.state == M7_MN_COLD);
    } else if (!strcmp(argv[1], "integrated_create_failure") || !strcmp(argv[1], "integrated_resume_failure")) {
        if (!strcmp(argv[1], "integrated_create_failure")) failCreate = 5; else failResume = 5;
        assert(Rk3572IntegratedInit());
        assert(deleted == (failCreate ? 4U : 5U));
        assert(Rk3572IntegratedInput("M7 status", 9) && strstr(reply, "ERROR not-ready"));
        input("PLK env-init", "ERROR not-ready");
    } else if (!strcmp(argv[1], "dormant")) dormant();
    else if (!strcmp(argv[1], "create_failure") || !strcmp(argv[1], "resume_failure") || !strcmp(argv[1], "delete_failure")) {
        failCreate = !strcmp(argv[1], "create_failure"); failResume = !failCreate;
        failDelete = !strcmp(argv[1], "delete_failure");
        assert(Rk3572PowerlinkInit() && Rk3572PowerlinkInit());
        assert(created == 1 && deleted == (failCreate ? 0U : 1U));
        input("PLK env-init", "ERROR not-ready");
    } else if (!strcmp(argv[1], "delay_failure") || !strcmp(argv[1], "delay_after_env")) {
        assert(!Rk3572PowerlinkInit());
        if (!strcmp(argv[1], "delay_after_env")) { input("PLK env-init", "ACCEPTED"); step(); }
        delayError = 1; step();
        assert(!app_status().ready && app_status().runtimeError == 104);
        if (!strcmp(argv[1], "delay_after_env")) {
            task = ownerId; assert(m7_plk_owner() && app_status().mn.state == M7_MN_IDLE); task = 1;
        }
        input("PLK env-init", "ERROR not-ready");
    } else if (!strcmp(argv[1], "owner_failure")) {
        assert(!Rk3572PowerlinkInit()); isr = 1; step(); isr = 0;
        assert(!app_status().ready && app_status().runtimeError == UINT32_MAX);
    } else if (!strcmp(argv[1], "masked_failure")) {
        assert(!Rk3572PowerlinkInit()); masked = 1; step(); masked = 0;
        assert(!app_status().ready && app_status().runtimeError == UINT32_MAX);
    } else if (!strcmp(argv[1], "stack_failure")) {
        task = 3; assert(!target_init()); task = 1; /* make real initialize fail */
        assert(!Rk3572PowerlinkInit()); input("PLK env-init", "ACCEPTED"); step();
        assert(app_status().mn.state == M7_MN_FAULT && !app_status().ready && app_status().result);
        input("PLK env-init", "ERROR not-ready");
    } else assert(0);
    assert(!locked && !timerAcquires && !ethAcquires && !writes);
    puts("P3b real owner/mailbox PASS: no prepare/timer/PHY/TX"); return 0;
}

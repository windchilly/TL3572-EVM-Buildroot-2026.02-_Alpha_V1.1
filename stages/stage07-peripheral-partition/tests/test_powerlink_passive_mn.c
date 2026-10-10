/* Real API/control/NMT/OD/CFM/PDO/EDRV/RTOS port, only hardware/RTOS mocked.
 * Native PASS is not physical ETH, timer IRQ, latency or CN interoperability. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <oplk/oplk.h>
#include <oplk/obdcdc.h>
#include <common/target.h>
#include <user/nmtu.h>
#include "m7_mn.h"
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
#include "m7_eth2_hw.h"
struct M7Eth2Dma m7_edrv_test_dma;
static uint32_t task = 1;
static int isr, masked, timerLease, ethLease, timerFail, timerStopFail, phyFail, stopFail;
static int semFail;
static uint64_t now;
static unsigned writes, sems, timerAcquires, ethAcquires, timerReleases, ethStops;
static unsigned allocations, failAllocation, live, frees;
static void* blocks[4096];
void* __real_malloc(size_t bytes);
void* __real_calloc(size_t count, size_t bytes);
void __real_free(void* pointer);
static void* remember(void* pointer)
{
    unsigned i;
    if (!pointer) return NULL;
    for (i = 0; i < 4096 && blocks[i]; ++i) {}
    assert(i < 4096); blocks[i] = pointer; ++live; return pointer;
}
void* __wrap_malloc(size_t bytes)
{
    if (++allocations == failAllocation) {
        fprintf(stderr, "injected malloc failure #%u bytes=%zu caller=%p\n", allocations, bytes, __builtin_return_address(0));
        return NULL;
    }
    return remember(__real_malloc(bytes));
}
void* __wrap_calloc(size_t count, size_t bytes)
{
    if (++allocations == failAllocation) {
        fprintf(stderr, "injected calloc failure #%u count=%zu bytes=%zu caller=%p\n", allocations, count, bytes, __builtin_return_address(0));
        return NULL;
    }
    return remember(__real_calloc(count, bytes));
}
void __wrap_free(void* pointer)
{
    unsigned i;
    if (!pointer) return;
    for (i = 0; i < 4096 && blocks[i] != pointer; ++i) {}
    assert(i < 4096); blocks[i] = NULL; --live; ++frees; __real_free(pointer);
}
int m7_plk_task_id(uint32_t* id) { *id = task; return 1; }
int m7_plk_in_interrupt(void) { return isr; }
int m7_plk_irq_enabled(void) { return !masked; }
uintptr_t m7_plk_irq_save(void) { int old = masked; masked = 1; return (uintptr_t)old; }
void m7_plk_irq_restore(uintptr_t old) { masked = (int)old; }
uint64_t m7_plk_milliseconds(void) { return now; }
int m7_plk_sleep(uint32_t ms) { (void)ms; assert(0); return 0; }
int m7_plk_sem_create(uint16_t* handle) { if (semFail) return 0; *handle = (uint16_t)++sems; return 1; }
int m7_plk_sem_take(uint16_t handle) { assert(handle && sems); return 1; }
int m7_plk_sem_give(uint16_t handle) { assert(handle && sems); return 1; }
int m7_plk_sem_delete(uint16_t handle) { assert(handle && sems); --sems; return 1; }
/* Host addresses cannot satisfy physical UP2 bounds. P2 tests the real range
 * helper separately; this is explicitly the mock cache-instruction boundary. */
int m7_plk_cache(const void* pointer, size_t bytes, int invalidate)
{ assert(pointer && bytes); (void)invalidate; return 1; }
int m7_plk_timer_acquire(uint32_t* frequency)
{ ++timerAcquires; if (timerFail || timerLease) return 0; timerLease = 1; *frequency = 24000000; return 1; }
int m7_plk_timer_release(void)
{ ++timerReleases; if (timerStopFail) return 0; timerLease = 0; return 1; }
uint64_t m7_plk_timer_now(void) { return now * 24000; }
void m7_plk_timer_arm(uint64_t deadline) { (void)deadline; assert(0); }
void m7_plk_timer_mask(void) {}
int m7_eth2_hw_acquire(void)
{ ++ethAcquires; if (phyFail || ethLease) return 0; ethLease = 1; return 1; }
int m7_eth2_hw_start(struct M7Eth2Dma* dma, const uint8_t mac[6])
{ assert(ethLease && dma == &m7_edrv_test_dma && mac[0] == 2); return 1; }
int m7_eth2_hw_stop(void)
{ ++ethStops; if (stopFail) return 0; ethLease = 0; return 1; }
uint32_t m7_eth2_hw_read(uint32_t offset) { assert(offset == 0x1160); return 0; }
void m7_eth2_hw_write(uint32_t offset, uint32_t value)
{ (void)offset; (void)value; ++writes; assert(0); /* No frame/tail doorbell in passive state. */ }
static M7MnStatus snapshot(void)
{ M7MnStatus out; assert(m7_mn_status(&out) == kErrorOk); return out; }
static void prepare_ok(void)
{
    uint32_t ret = m7_mn_prepare();
    if (ret != kErrorOk) {
        M7MnStatus out = snapshot();
        fprintf(stderr, "prepare failed rc=0x%x state=%u last=0x%x target_fault=%d heap=%u sem=%u ETH=%d timer=%d\n",
            ret, out.state, out.lastError, m7_plk_faulted(), live, sems, ethLease, timerLease);
    }
    assert(ret == kErrorOk);
}
static void passive(void)
{
    unsigned i;
    uint32_t value;
    size_t bytes;
    assert(m7_mn_initialize() == kErrorOk);
    assert(snapshot().state == M7_MN_IDLE && !ethLease && !timerLease);
    for (i = 0; i < 100; ++i) {
        prepare_ok();
        assert(snapshot().state == M7_MN_PREPARED && ethLease && timerLease);
        bytes = sizeof(value); value = 0;
        assert(oplk_readLocalObject(0x1f82, 0, &value, &bytes) == kErrorOk);
        assert(!(value & NMT_FEATUREFLAGS_PRC)); /* Disabled is not advertised. */
        assert((value & (NMT_FEATUREFLAGS_CFM | NMT_FEATUREFLAGS_ISOCHR | NMT_FEATUREFLAGS_SDO_ASND)) ==
                       (NMT_FEATUREFLAGS_CFM | NMT_FEATUREFLAGS_ISOCHR | NMT_FEATUREFLAGS_SDO_ASND));
        value = 2000; assert(oplk_writeLocalObject(0x1006, 0, &value, sizeof(value)) == kErrorOk);
        assert(obdcdc_loadCdc() == kErrorOk); /* REAL memory CDC parsing/OD write. */
        bytes = sizeof(value); value = 0;
        assert(oplk_readLocalObject(0x1006, 0, &value, &bytes) == kErrorOk && value == 1000);
        assert(nmtu_getNmtState() == kNmtGsOff);
        now += 10; assert(m7_mn_process() == kErrorOk);
        assert(nmtu_getNmtState() == kNmtGsOff && !writes);
        assert(m7_mn_stop() == kErrorOk);
        assert(!timerLease && !ethLease && !sems && !live);
    }
    assert(snapshot().processes == 100);
    assert(m7_mn_exit() == kErrorOk && !m7_plk_owner());
    assert(m7_mn_initialize() == kErrorOk && m7_mn_exit() == kErrorOk);
    printf("real stack 100 passive prepare/process/stop: allocations=%u frees=%u live=%u; no TX/NMT reset\n", allocations, frees, live);
}
static void owner_test(void)
{
    M7MnStatus out;
    assert(m7_mn_initialize() == kErrorOk);
    task = 2;
    assert(m7_mn_prepare() == kErrorInvalidOperation);
    assert(m7_mn_status(&out) == kErrorInvalidOperation);
    assert(m7_mn_exit() == kErrorInvalidOperation);
    task = 1; isr = 1; assert(m7_mn_prepare() == kErrorInvalidOperation);
    isr = 0; masked = 1; assert(m7_mn_prepare() == kErrorInvalidOperation);
    masked = 0; assert(!timerAcquires && !ethAcquires);
    prepare_ok();
    task = 2; assert(m7_mn_process() == kErrorInvalidOperation);
    assert(m7_mn_stop() == kErrorInvalidOperation);
    task = 1; assert(m7_mn_stop() == kErrorOk && m7_mn_exit() == kErrorOk);
}
static void cdc_test(void)
{
    uint8_t data[] = {1,0,0,0, 6,0x10,0, 4,0,0,0, 0xe8,3,0,0};
    size_t i;
    assert(m7_mn_cdc_valid(data, sizeof(data)));
    assert(!m7_mn_cdc_valid(NULL, sizeof(data)));
    assert(!m7_mn_cdc_valid(data, 16385));
    for (i = 0; i < sizeof(data); ++i) assert(!m7_mn_cdc_valid(data, i));
    data[0] = 0; assert(!m7_mn_cdc_valid(data, sizeof(data)));
    data[0] = 65; assert(!m7_mn_cdc_valid(data, sizeof(data)));
    data[0] = 1; data[7] = 0; assert(!m7_mn_cdc_valid(data, sizeof(data)));
    memset(data+7, 255, 4); assert(!m7_mn_cdc_valid(data, sizeof(data)));
    data[7] = 3; data[8] = data[9] = data[10] = 0;
    assert(!m7_mn_cdc_valid(data, sizeof(data))); /* Reject trailing bytes. */
}
static void terminal(void)
{
    unsigned savedFrees = frees, savedEth = ethAcquires, savedTimer = timerAcquires;
    assert(snapshot().state == M7_MN_FAULT);
    assert(m7_mn_prepare() == kErrorInvalidOperation);
    assert(m7_mn_process() == kErrorInvalidOperation);
    assert(m7_mn_stop() == kErrorInvalidOperation);
    assert(m7_mn_exit() == kErrorInvalidOperation);
    assert(m7_mn_initialize() == kErrorInvalidOperation);
    assert(frees == savedFrees && ethAcquires == savedEth && timerAcquires == savedTimer);
}
int main(int argc, char** argv)
{
    unsigned before;
    assert(argc == 2);
    if (!strcmp(argv[1], "passive")) passive();
    else if (!strcmp(argv[1], "owner")) owner_test();
    else if (!strcmp(argv[1], "cdc")) cdc_test();
    else if (!strcmp(argv[1], "target_failure")) {
        assert(target_init() == kErrorOk);
        assert(m7_mn_initialize() == kErrorInvalidOperation);
        assert(!timerAcquires && !ethAcquires && !allocations); terminal();
    } else {
        assert(m7_mn_initialize() == kErrorOk);
        if (!strcmp(argv[1], "timer_failure")) timerFail = 1;
        else if (!strcmp(argv[1], "phy_failure")) phyFail = 1;
        else if (!strcmp(argv[1], "sem_failure")) semFail = 1;
        else if (!strncmp(argv[1], "allocation_failure_", 19)) {
            unsigned position = (unsigned)atoi(argv[1] + 19);
            assert(position >= 1 && position <= 16); failAllocation = allocations + position;
        }
        else {
            prepare_ok(); before = frees;
            if (!strcmp(argv[1], "stop_failure")) stopFail = 1;
            else { assert(!strcmp(argv[1], "timer_stop_failure")); timerStopFail = 1; }
            assert(m7_mn_stop() != kErrorOk);
            assert(frees == before && sems && live && timerLease);
            if (stopFail) assert(ethLease && !timerReleases);
            else assert(!ethLease);
            terminal(); printf("%s retained resources: heap=%u sem=%u ETH=%d timer=%d\n", argv[1], live, sems, ethLease, timerLease);
            return 0;
        }
        assert(m7_mn_prepare() != kErrorOk); terminal();
    }
    printf("PASS mn_%s (software only)\n", argv[1]); return 0;
}

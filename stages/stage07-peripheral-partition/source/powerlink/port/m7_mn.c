/* P3a passive full-stack integration. Hardware acquisition is NOT boot passive:
 * prepare touches GMAC/PHY/CNTP; only an explicitly selected candidate may call
 * it after host handoff. Partial init/failed stop is terminal until reboot.
 * Do not add SwReset, SwitchOff or network commands before hardware acceptance.
 */
#include <oplk/oplk.h>
#include <obdcreate/obdcreate.h>
#include "m7_mn.h"
#include "m7_edrv.h"
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"

static M7MnStatus status;
static int entered;
/* One local OD entry, NOT a CN/device/PDO plan. 1000 us is a software value,
 * not a measured timing capability. Buffer lifetime covers the whole stack. */
static const uint8_t cdc[] = {1,0,0,0, 6,0x10,0, 4,0,0,0, 0xe8,3,0,0};
static uint32_t le32(const uint8_t* p)
{ return (uint32_t)p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24); }
int m7_mn_cdc_valid(const uint8_t* data, size_t length)
{
    uint32_t count, i, bytes;
    size_t offset = 4;
    if (!data || length < 4 || length > 16384) return 0;
    count = le32(data);
    if (!count || count > 64) return 0;
    for (i = 0; i < count; ++i) {
        if (length - offset < 7) return 0;
        bytes = le32(data + offset + 3); offset += 7;
        if (!bytes || bytes > length - offset) return 0;
        offset += bytes;
    }
    return offset == length;
}
static int owner(void)
{
    uint32_t task;
    return !entered && !m7_plk_in_interrupt() && m7_plk_irq_enabled() &&
        m7_plk_task_id(&task) && task == status.owner;
}
static uint32_t fault(tOplkError error)
{
    status.lastError = (uint32_t)error; status.state = M7_MN_FAULT;
    m7_plk_fault(); entered = 0;
    return (uint32_t)error;
}
static tOplkError event(tOplkApiEventType type, const tOplkApiEventArg* arg, void* user)
{
    (void)user;
    ++status.events; status.lastEvent = (uint32_t)type;
    if (type == kOplkApiEventNmtStateChange) status.nmtState = (uint32_t)arg->nmtStateChange.newNmtState;
    if (type == kOplkApiEventCriticalError) {
        status.lastError = (uint32_t)arg->internalError.oplkError;
        status.state = M7_MN_FAULT; m7_plk_fault();
    }
    return kErrorOk;
}
uint32_t m7_mn_initialize(void)
{
    tOplkError ret;
    if (status.state != M7_MN_COLD || entered || m7_plk_in_interrupt() ||
        !m7_plk_irq_enabled() || !m7_plk_task_id(&status.owner)) return kErrorInvalidOperation;
    entered = 1; ret = oplk_initialize();
    if (ret != kErrorOk) return fault(ret);
    entered = 0; status.state = M7_MN_IDLE; return kErrorOk;
}
uint32_t m7_mn_prepare(void)
{
    tOplkApiInitParam init;
    tOplkError ret;
    uint32_t cycle = 1000;
    if (!owner() || status.state != M7_MN_IDLE || !m7_plk_ready()) return kErrorInvalidOperation;
    entered = 1; memset(&init, 0, sizeof(init));
    init.sizeOfInitParam = sizeof(init); init.nodeId = 0xf0;
    memcpy(init.aMacAddress, (const uint8_t[]){2,0x55,0x50,0x32,0,2}, 6);
    init.hwParam.pDevName = "UP2-ETH2"; init.featureFlags = UINT32_MAX;
    init.cycleLen = cycle; init.isochrTxMaxPayload = 256; init.isochrRxMaxPayload = 1490;
    init.presMaxLatency = 50000; init.preqActPayloadLimit = 36; init.presActPayloadLimit = 36;
    init.asndMaxLatency = 150000; init.asyncMtu = 1500; init.prescaler = 2;
    init.lossOfFrameTolerance = 500000; init.asyncSlotTimeout = 3000000;
    init.waitSocPreq = UINT32_MAX; init.deviceType = UINT32_MAX;
    init.vendorId = UINT32_MAX; init.productCode = UINT32_MAX;
    init.revisionNumber = UINT32_MAX; init.serialNumber = UINT32_MAX;
    init.syncNodeId = C_ADR_SYNC_ON_SOC; init.pfnCbEvent = event;
    ret = obdcreate_initObd(&init.obdInitParam);
    if (ret == kErrorOk) ret = oplk_create(&init);
    if (ret == kErrorOk && !m7_mn_cdc_valid(cdc, sizeof(cdc))) ret = kErrorObdInvalidDcf;
    if (ret == kErrorOk) ret = oplk_setCdcBuffer(cdc, sizeof(cdc));
    /* No reset: exercise OD access without moving NMT out of GsOff. */
    if (ret == kErrorOk) ret = oplk_writeLocalObject(0x1006, 0, &cycle, sizeof(cycle));
    if (ret != kErrorOk || !m7_plk_ready()) return fault(ret == kErrorOk ? kErrorInvalidOperation : ret);
    status.state = M7_MN_PREPARED; entered = 0; return kErrorOk;
}
uint32_t m7_mn_process(void)
{
    tOplkError ret;
    if (!owner() || status.state != M7_MN_PREPARED || !m7_plk_ready()) return kErrorInvalidOperation;
    entered = 1;
    ret = m7_hrestimer_process();
    if (ret == kErrorOk) ret = m7_edrv_poll(8);
    if (ret == kErrorOk) ret = oplk_process();
    if (ret != kErrorOk || !m7_plk_ready() || status.state == M7_MN_FAULT)
        return fault(ret == kErrorOk ? kErrorInvalidOperation : ret);
    ++status.processes; entered = 0; return kErrorOk;
}
uint32_t m7_mn_stop(void)
{
    tOplkError ret;
    if (!owner() || status.state != M7_MN_PREPARED || !m7_plk_ready()) return kErrorInvalidOperation;
    entered = 1; ret = oplk_destroy();
    if (ret != kErrorOk || !m7_plk_ready()) return fault(ret == kErrorOk ? kErrorInvalidOperation : ret);
    status.state = M7_MN_IDLE; entered = 0; return kErrorOk;
}
uint32_t m7_mn_exit(void)
{
    if (!owner() || status.state != M7_MN_IDLE || !m7_plk_ready()) return kErrorInvalidOperation;
    entered = 1; oplk_exit();
    if (m7_plk_owner() || m7_plk_faulted()) return fault(kErrorInvalidOperation);
    status.state = M7_MN_COLD; entered = 0; return kErrorOk;
}
uint32_t m7_mn_status(M7MnStatus* out)
{
    if (!out || !owner()) return kErrorInvalidOperation;
    *out = status; return kErrorOk;
}

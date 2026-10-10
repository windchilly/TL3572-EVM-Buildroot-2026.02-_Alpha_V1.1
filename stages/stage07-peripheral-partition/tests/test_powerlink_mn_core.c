/* No hardware: exercise the actual upstream NMT module with observed sinks. */
#include <assert.h>
#include <stdio.h>
#include <common/ami.h>
#include <kernel/nmtk.h>
#include <kernel/dllk.h>
#include <kernel/eventk.h>

static tNmtState state = kNmtGsOff;
static unsigned transitions;
static unsigned user_events;

tOplkError dllk_process(const tEvent* event)
{
    assert(event->eventType == kEventTypeNmtStateChange);
    assert(event->eventSink == kEventSinkDllk);
    assert(event->eventArgSize == sizeof(tEventNmtStateChange));
    const tEventNmtStateChange* change = event->eventArg.pEventArg;
    assert(change->oldNmtState == state);
    state = change->newNmtState;
    ++transitions;
    return kErrorOk;
}

tOplkError eventk_postEvent(const tEvent* event)
{
    assert(event->eventSink == kEventSinkNmtu);
    assert(((const tEventNmtStateChange*)event->eventArg.pEventArg)->newNmtState == state);
    ++user_events;
    return kErrorOk;
}

static void step(tNmtEvent nmt_event, tNmtState expected)
{
    tEvent event = {0};
    event.eventType = kEventTypeNmtEvent;
    event.eventArgSize = sizeof(nmt_event);
    event.eventArg.pEventArg = &nmt_event;
    assert(nmtk_process(&event) == kErrorOk);
    if (state != expected) {
        fprintf(stderr, "event=0x%x actual=0x%x expected=0x%x\n", nmt_event, state, expected);
    }
    assert(state == expected);
    assert(transitions == user_events);
}

static void boot(void)
{
    step(kNmtEventSwReset, kNmtGsInitialising);
    step(kNmtEventEnterResetApp, kNmtGsResetApplication);
    step(kNmtEventEnterResetCom, kNmtGsResetCommunication);
    step(kNmtEventEnterResetConfig, kNmtGsResetConfiguration);
    step(kNmtEventEnterMsNotActive, kNmtMsNotActive);
    step(kNmtEventTimerMsPreOp1, kNmtMsPreOperational1);
}

int main(void)
{
    /* Check the LP64 ABI and endian helpers actually used by the wire codec. */
    assert(sizeof(UINT32) == 4 && sizeof(ULONG) == 8 && sizeof(void*) == 8);
    assert(!CHECK_IF_BIG_ENDIAN());
    UINT8 bytes[10] = {0};
    ami_setUint32Le(bytes + 1, 0x12345678U);
    assert(bytes[1] == 0x78 && bytes[4] == 0x12);
    assert(ami_getUint32Le(bytes + 1) == 0x12345678U);
    ami_setUint16Be(bytes + 1, 0x88abU);
    assert(bytes[1] == 0x88 && bytes[2] == 0xab);
    assert(ami_getUint16Be(bytes + 1) == 0x88abU);

    assert(nmtk_init() == kErrorOk);
    boot();
    /* Timer and mandatory-node identification must both arrive, in either order. */
    step(kNmtEventTimerMsPreOp2, kNmtMsPreOperational1);
    step(kNmtEventAllMandatoryCNIdent, kNmtMsPreOperational2);
    step(kNmtEventEnterReadyToOperate, kNmtMsReadyToOperate);
    step(kNmtEventEnterMsOperational, kNmtMsOperational);
    step(kNmtEventNmtCycleError, kNmtMsPreOperational1);
    step(kNmtEventInternComError, kNmtGsResetCommunication);
    step(kNmtEventSwitchOff, kNmtGsOff);
    boot();
    step(kNmtEventAllMandatoryCNIdent, kNmtMsPreOperational1);
    step(kNmtEventTimerMsPreOp2, kNmtMsPreOperational2);
    step(kNmtEventDllCeSoc, kNmtGsResetCommunication);
    step(kNmtEventCriticalError, kNmtGsOff);
    tEvent invalid = {0};
    assert(nmtk_process(&invalid) == kErrorNmtInvalidEvent);
    assert(nmtk_exit() == kErrorOk);
    printf("PASS: upstream MN boot/gates/operational/cycle-error/reset/conflicting-MN; %u state changes; LP64/unaligned AMI; no HAL or frames\n", transitions);
    return 0;
}

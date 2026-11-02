/* Actual mailbox/worker/serialization; guard mocked here, real guard separately. */
#define M7_OWNER_TEST_MAIN OwnerRegressionMain
#include "test_powerlink_owner.c"
static unsigned cycles;
static int unsafe;
uint32_t m7_timer_probe(M7TimerProbeResult* out) { *out=(M7TimerProbeResult){0};out->clean=1;return 0; }
uint32_t m7_eth_probe(M7EthProbeResult* out) { *out=(M7EthProbeResult){0};out->clean=1;return 0; }
uint32_t m7_edrv_probe(M7EdrvProbeResult* out) { *out=(M7EdrvProbeResult){0};out->clean=1;return 0; }
uint32_t m7_mn_probe(M7MnProbeResult* out) { *out=(M7MnProbeResult){0};out->clean=1;return 0; }
uint32_t m7_nmt_probe(M7NmtProbeResult* out) { *out=(M7NmtProbeResult){0};out->lifecycle.clean=1;return 0; }
uint32_t m7_cycle_probe(M7CycleProbeResult* out)
{
    M7CycleProbeResult unavailable;
    assert(task==ownerId && !locked && !isr && !masked); ++cycles;
    assert(!Rk3572PowerlinkCycleSnapshot(&unavailable));
    input("PLK cycle-status","cycle-unavailable"); input("PLK cycle-probe","ERROR busy");
    *out=(M7CycleProbeResult){0};out->abi=1;out->bytes=sizeof(*out);
    out->lifecycle.clean=!unsafe;out->lifecycle.stage=unsafe?4:9;
    out->lifecycle.result=unsafe?M7_CYCLE_PENDING:0;
    out->reached=0x2fd;out->resetSubmitted=1;out->offSubmitted=!unsafe;out->stopCycleCalls=!unsafe;
    out->contextValid=1;out->watchdogTrips=unsafe;return out->lifecycle.result;
}
static void nested(void)
{
    uint32_t before=app_status().submitted;
    assert(Rk3572PowerlinkInput("PLK cycle-probe",15));
    assert(app_status().submitted==before);
}
int main(int argc,char** argv)
{
    M7CycleProbeResult out;
    assert(argc==2 && sizeof(M7PowerlinkSnapshot)==1504 && !Rk3572PowerlinkInit());
    assert(!Rk3572PowerlinkCycleSnapshot(NULL));
    input("PLK status","mode=bounded-cycle-diagnostic"); input("PLK cycle-status","cycle-unavailable");
    assert(!cycles && !allocations && !ethAcquires && !timerAcquires);
    if (!strcmp(argv[1],"invalid")) {
        input("PLK cycle-probe\n\n","invalid-command"); input("PLK cycle-run","invalid-command");
        assert(Rk3572PowerlinkInput("PLK cycle-probe\0x",17) && strstr(reply,"invalid-command"));
        input("PLK env-init","ACCEPTED");step();input("PLK cycle-probe","ERROR wrong-state");
        assert(!cycles);return 0;
    }
    if (!strcmp(argv[1],"reentrant")) { sendHook=nested;input("PLK status","seq=0");assert(!app_status().submitted); }
    if (!strcmp(argv[1],"unsafe")) unsafe=1;
    input("PLK cycle-probe","ACCEPTED seq=1");input("PLK nmt-probe","ERROR busy");step();
    assert(cycles==1 && app_status().completed==1 && Rk3572PowerlinkCycleSnapshot(&out));
    input("PLK cycle-status",unsafe?"clean=0 stage=4":"clean=1 stage=9");
    assert(strlen(reply)<384 && out.abi==1 && out.bytes==sizeof(out));
    input("PLK cycle-probe",unsafe?"ERROR not-ready":"ERROR cycle-consumed");
    assert(cycles==1 && app_status().submitted==1 && !writes && !ethAcquires && !timerAcquires);
    puts("P3j owner mailbox one-shot/BSS ABI/busy/fault/serialization PASS; guard mocked, NO BOARD");return 0;
}

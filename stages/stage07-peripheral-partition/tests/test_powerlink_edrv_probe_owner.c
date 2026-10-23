#define M7_OWNER_TEST_MAIN OwnerRegressionMain
#include "test_powerlink_owner.c"
static unsigned ethProbes, timerProbes, edrvProbes;
static int unsafe;
uint32_t m7_timer_probe(M7TimerProbeResult* out)
{ assert(task == ownerId && !locked); ++timerProbes; *out = (M7TimerProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_eth_probe(M7EthProbeResult* out)
{ assert(task == ownerId && !locked); ++ethProbes; *out = (M7EthProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_edrv_probe(M7EdrvProbeResult* out)
{
    assert(task == ownerId && !isr && !masked && !locked && !m7_plk_owner()); ++edrvProbes;
    *out = (M7EdrvProbeResult){0}; out->clean = !unsafe;
    out->received = out->submitted = out->completed = out->fcs = 64;
    return out->result = unsafe ? M7_EPROBE_CLEANUP : M7_EPROBE_OK;
}
int main(int argc, char** argv)
{
    unsigned i; assert(argc == 2 && !Rk3572PowerlinkInit());
    if (!strcmp(argv[1], "normal")) {
        for (i = 0; i < 100; ++i) {
            input("PLK edrv-probe", "ACCEPTED"); input("PLK env-init", "ERROR busy"); step();
            input("PLK edrv-status", "rx=64 submitted=64 tx=64 fcs=64");
            input("PLK timer-probe", "ACCEPTED"); step(); input("PLK eth-probe", "ACCEPTED"); step();
            assert(app_status().ready && app_status().mn.state == M7_MN_COLD);
        }
        assert(edrvProbes == 100 && timerProbes == 100 && ethProbes == 100 && app_status().completed == 300);
        input("PLK env-init", "ACCEPTED"); step(); input("PLK edrv-probe", "ERROR wrong-state");
        input("PLK env-exit", "ACCEPTED"); step();
    } else if (!strcmp(argv[1], "unsafe")) {
        unsafe = 1; input("PLK edrv-probe", "ACCEPTED"); step(); assert(!app_status().ready);
        input("PLK edrv-probe", "ERROR not-ready"); input("PLK timer-probe", "ERROR not-ready");
        input("PLK edrv-status", "clean=0");
    } else if (!strcmp(argv[1], "invalid")) {
        input("PLK edrv-probe\n\n", "invalid-command");
        assert(Rk3572PowerlinkInput("PLK edrv-probe\0x", 16) && strstr(reply, "invalid-command"));
        input("PLK edrv-prob", "invalid-command"); input("PLK reset", "invalid-command"); assert(!edrvProbes);
    } else assert(0);
    assert(!allocations && !timerAcquires && !ethAcquires && !writes);
    puts("P3e cumulative mailbox native PASS"); return 0;
}

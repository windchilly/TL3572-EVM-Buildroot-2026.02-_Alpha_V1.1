#define M7_OWNER_TEST_MAIN OwnerRegressionMain
#include "test_powerlink_owner.c"
static unsigned mnProbes;
static int unsafe;
uint32_t m7_timer_probe(M7TimerProbeResult* out)
{ assert(task == ownerId && !locked); *out = (M7TimerProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_eth_probe(M7EthProbeResult* out)
{ assert(task == ownerId && !locked); *out = (M7EthProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_edrv_probe(M7EdrvProbeResult* out)
{ assert(task == ownerId && !locked); *out = (M7EdrvProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_mn_probe(M7MnProbeResult* out)
{
    assert(task == ownerId && !isr && !masked && !locked && !m7_plk_owner()); ++mnProbes;
    *out = (M7MnProbeResult){0}; out->clean = !unsafe; out->loops = 128; out->stage = 5;
    out->final.state = unsafe ? M7_MN_FAULT : M7_MN_COLD;
    return out->result = unsafe ? M7_MPROBE_STOP : M7_MPROBE_OK;
}
int main(int argc, char** argv)
{
    unsigned i; assert(argc == 2 && !Rk3572PowerlinkInit());
    if (!strcmp(argv[1], "normal")) {
        for (i = 0; i < 100; ++i) {
            input("PLK mn-probe", "ACCEPTED"); input("PLK env-init", "ERROR busy"); step();
            input("PLK mn-status", "clean=1 stage=5");
            input("PLK timer-probe", "ACCEPTED"); step(); input("PLK eth-probe", "ACCEPTED"); step();
            input("PLK edrv-probe", "ACCEPTED"); step();
            assert(app_status().ready && app_status().mn.state == M7_MN_COLD);
        }
        assert(mnProbes == 100 && app_status().completed == 400);
        input("PLK env-init", "ACCEPTED"); step(); input("PLK mn-probe", "ERROR wrong-state");
        input("PLK env-exit", "ACCEPTED"); step();
    } else if (!strcmp(argv[1], "unsafe")) {
        unsafe = 1; input("PLK mn-probe", "ACCEPTED"); step(); assert(!app_status().ready);
        input("PLK mn-probe", "ERROR not-ready"); input("PLK edrv-probe", "ERROR not-ready");
        input("PLK mn-status", "clean=0");
    } else if (!strcmp(argv[1], "invalid")) {
        input("PLK mn-probe\n\n", "invalid-command");
        assert(Rk3572PowerlinkInput("PLK mn-probe\0x", 14) && strstr(reply, "invalid-command"));
        input("PLK mn-prob", "invalid-command"); input("PLK reset", "invalid-command"); assert(!mnProbes);
    } else assert(0);
    assert(!allocations && !timerAcquires && !ethAcquires && !writes);
    puts("P3f cumulative mailbox native PASS"); return 0;
}

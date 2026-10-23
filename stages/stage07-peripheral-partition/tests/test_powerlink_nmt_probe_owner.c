/* Real cumulative owner/parser, mocked probe only; real probe tested separately. */
#define M7_OWNER_TEST_MAIN OwnerRegressionMain
#include "test_powerlink_owner.c"
static unsigned nmtProbes;
static int unsafe;
uint32_t m7_timer_probe(M7TimerProbeResult* out)
{ assert(task == ownerId && !locked); *out = (M7TimerProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_eth_probe(M7EthProbeResult* out)
{ assert(task == ownerId && !locked); *out = (M7EthProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_edrv_probe(M7EdrvProbeResult* out)
{ assert(task == ownerId && !locked); *out = (M7EdrvProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_mn_probe(M7MnProbeResult* out)
{ assert(task == ownerId && !locked); *out = (M7MnProbeResult){0}; out->clean = 1; return 0; }
uint32_t m7_nmt_probe(M7NmtProbeResult* out)
{
    assert(task == ownerId && !isr && !masked && !locked && !m7_plk_owner()); ++nmtProbes;
    *out = (M7NmtProbeResult){0}; out->lifecycle.clean = !unsafe; out->lifecycle.stage = 6;
    out->resetSubmitted = 1; out->offSubmitted = 1; out->resetLoops = 5; out->offLoops = 1; out->reached = kNmtMsNotActive;
    out->lifecycle.final.state = unsafe ? M7_MN_FAULT : M7_MN_COLD;
    return out->lifecycle.result = unsafe ? M7_MPROBE_STOP : 0;
}
static void reenter(void)
{
    M7PowerlinkSnapshot before = app_status();
    assert(Rk3572PowerlinkInput("PLK nmt-probe", 13));
    assert(app_status().submitted == before.submitted);
}
int main(int argc, char** argv)
{
    unsigned i; assert(argc == 2 && !Rk3572PowerlinkInit());
    step(); input("PLK status", "mode=bounded-NMT-diagnostic"); assert(!nmtProbes);
    if (!strcmp(argv[1], "normal")) {
        for (i = 0; i < 100; ++i) {
            input("PLK nmt-probe", "ACCEPTED"); input("PLK mn-probe", "ERROR busy"); step();
            input("PLK nmt-status", "clean=1 stage=6");
            assert(strlen(reply) < 384 && strstr(reply, "reset=1 off=1 resetLoops=5 offLoops=1 reached=0x21c"));
            input("PLK mn-probe", "ACCEPTED"); step();
            assert(app_status().ready && app_status().mn.state == M7_MN_COLD);
        }
        assert(nmtProbes == 100 && app_status().completed == 200);
        input("PLK env-init", "ACCEPTED"); step(); input("PLK nmt-probe", "ERROR wrong-state");
        input("PLK env-exit", "ACCEPTED"); step();
    } else if (!strcmp(argv[1], "unsafe")) {
        unsafe = 1; input("PLK nmt-probe", "ACCEPTED"); step(); assert(!app_status().ready);
        input("PLK nmt-probe", "ERROR not-ready"); input("PLK mn-probe", "ERROR not-ready");
        input("PLK nmt-status", "clean=0");
    } else if (!strcmp(argv[1], "reentrant")) {
        sendHook = reenter; input("PLK status", "seq=0"); assert(!nmtProbes && !app_status().submitted);
    } else if (!strcmp(argv[1], "invalid")) {
        input("PLK nmt-probe\n\n", "invalid-command"); input("PLK nmt-reset", "invalid-command");
        input("PLK start", "invalid-command");
        assert(Rk3572PowerlinkInput("PLK nmt-probe\0x", 15) && strstr(reply, "invalid-command") && !nmtProbes);
    } else assert(0);
    assert(!allocations && !timerAcquires && !ethAcquires && !writes);
    puts("P3g cumulative mailbox PASS"); return 0;
}

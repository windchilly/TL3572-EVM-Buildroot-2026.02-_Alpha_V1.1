/* Real cumulative owner/mailbox + full stack, probe hardware mocked. */
#define M7_OWNER_TEST_MAIN OwnerRegressionMain
#include "test_powerlink_owner.c"
static unsigned ethProbes, timerProbes;
static int unsafe;
uint32_t m7_timer_probe(M7TimerProbeResult* out)
{
    assert(task == ownerId && !isr && !masked && !locked && !m7_plk_owner()); ++timerProbes;
    *out = (M7TimerProbeResult){0}; out->clean = 1; out->samples = 24;
    out->after.interrupts = out->callbacks = 24; return 0;
}
uint32_t m7_eth_probe(M7EthProbeResult* out)
{
    assert(task == ownerId && !isr && !masked && !locked && !m7_plk_owner()); ++ethProbes;
    *out = (M7EthProbeResult){0}; out->clean = !unsafe;
    out->configured = (M7EthHardware){0x7b74,0x4412,0x2000,0x2004,0xc000,0,0,0,0,0};
    return out->result = unsafe ? M7_ETH_CLEANUP : M7_ETH_OK;
}
int main(int argc, char** argv)
{
    unsigned i; assert(argc == 2 && !Rk3572PowerlinkInit());
    if (!strcmp(argv[1], "normal")) {
        for (i = 0; i < 100; ++i) {
            input("PLK timer-probe", "ACCEPTED"); input("PLK eth-probe", "ERROR busy"); step();
            input("PLK eth-probe", "ACCEPTED"); input("PLK env-init", "ERROR busy"); step();
            assert(app_status().ready && app_status().mn.state == M7_MN_COLD);
            input("PLK eth-status", "bmcr=0x2000 bmsr=0x2004 mac=0xc000");
            input("PLK timer-status", "irqs=24 callbacks=24");
        }
        assert(ethProbes == 100 && timerProbes == 100 && app_status().completed == 200);
        input("PLK env-init", "ACCEPTED"); step(); input("PLK eth-probe", "ERROR wrong-state");
        input("PLK env-exit", "ACCEPTED"); step();
    } else if (!strcmp(argv[1], "unsafe")) {
        unsafe = 1; input("PLK eth-probe", "ACCEPTED"); step(); assert(!app_status().ready);
        input("PLK eth-probe", "ERROR not-ready"); input("PLK timer-probe", "ERROR not-ready");
        input("PLK eth-status", "clean=0");
    } else if (!strcmp(argv[1], "invalid")) {
        input("PLK eth-probe\n\n", "invalid-command");
        assert(Rk3572PowerlinkInput("PLK eth-probe\0x", 15) && strstr(reply, "invalid-command"));
        input("PLK eth-prob", "invalid-command"); input("PLK reset", "invalid-command");
        assert(!ethProbes && !timerProbes);
    } else assert(0);
    assert(!allocations && !timerAcquires && !ethAcquires && !writes);
    puts("P3d cumulative ETH+timer mailbox native PASS"); return 0;
}

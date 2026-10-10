/* Real mailbox/owner; probe is mocked here and tested separately above. */
#define M7_OWNER_TEST_MAIN OwnerRegressionMain
#include "test_powerlink_owner.c"
static unsigned probes;
static int unsafe;
uint32_t m7_timer_probe(M7TimerProbeResult* out)
{
    assert(task == ownerId && !isr && !masked && !locked && !m7_plk_owner()); ++probes;
    *out = (M7TimerProbeResult){0}; out->clean = !unsafe; out->samples = 24;
    out->after.interrupts = out->callbacks = 24; out->after.frequency = 24000000;
    return out->result = unsafe ? M7_TIMER_CLEANUP : M7_TIMER_OK;
}
int main(int argc, char** argv)
{
    unsigned i; assert(argc == 2 && !Rk3572PowerlinkInit());
    if (!strcmp(argv[1], "normal")) {
        for (i = 0; i < 100; ++i) {
            input("PLK timer-probe", "ACCEPTED"); input("PLK env-init", "ERROR busy"); step();
            assert(app_status().mn.state == M7_MN_COLD && app_status().ready);
            input("PLK timer-status", "irqs=24 callbacks=24");
        }
        input("PLK env-init", "ACCEPTED"); step(); input("PLK timer-probe", "ERROR wrong-state");
        input("PLK env-exit", "ACCEPTED"); step(); assert(probes == 100);
    } else if (!strcmp(argv[1], "unsafe")) {
        unsafe = 1; input("PLK timer-probe", "ACCEPTED"); step(); assert(!app_status().ready);
        input("PLK timer-probe", "ERROR not-ready"); input("PLK timer-status", "clean=0");
    } else if (!strcmp(argv[1], "invalid")) {
        input("PLK timer-probe\n\n", "invalid-command");
        assert(Rk3572PowerlinkInput("PLK timer-probe\0x", 17) && strstr(reply, "invalid-command"));
        input("PLK timer-prob", "invalid-command"); assert(!probes);
    } else assert(0);
    assert(!allocations && !timerAcquires && !ethAcquires && !writes);
    puts("P3c timer mailbox native PASS"); return 0;
}

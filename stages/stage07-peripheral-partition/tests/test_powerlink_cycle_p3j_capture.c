/* Capture the actual native production result; all hardware is still mocked.
 * Historical harness unchanged. Never used to create hardware evidence. */
#define m7_cycle_probe P3jRecordedProbe
#include "test_powerlink_cycle_probe.c"
#undef m7_cycle_probe
uint32_t m7_cycle_probe(M7CycleProbeResult* out);
uint32_t P3jRecordedProbe(M7CycleProbeResult* out)
{
    uint32_t rc=m7_cycle_probe(out);
    const char* path=getenv("M7_P3J_NATIVE_CAPTURE");
    if (path && !rc && out->lifecycle.clean) {
        FILE* stream=fopen(path,"wbx"); assert(stream);
        assert(fwrite(out,1,sizeof(*out),stream)==sizeof(*out)); assert(!fclose(stream));
    }
    return rc;
}

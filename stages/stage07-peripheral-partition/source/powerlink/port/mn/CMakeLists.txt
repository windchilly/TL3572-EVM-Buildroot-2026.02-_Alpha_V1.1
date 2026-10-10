cmake_minimum_required(VERSION 3.16)
project(m7_powerlink_passive_mn C)
set(port "${CMAKE_CURRENT_SOURCE_DIR}/..")
# Caller prepares a separate source tree and applies 0003. P0/P1/P2 stay intact.
add_subdirectory("${port}" "core")
add_library(m7_powerlink_passive_mn STATIC
    "${port}/m7_mn.c" "${port}/edrv-rk3572.c"
    "${port}/target-uniproton.c" "${port}/hrestimer-rk3572.c"
    "${OPLK_SOURCE}/apps/common/src/obdcreate/obdcreate.c")
target_include_directories(m7_powerlink_passive_mn PUBLIC
    "${OPLK_SOURCE}/apps/common/src" "${OPLK_SOURCE}/apps/common/objdicts/CiA302-4_MN")
target_link_libraries(m7_powerlink_passive_mn PUBLIC m7_powerlink_mn_core)
# Upstream embedded MN app supplies this explicitly for generated OD tables;
# the core uses the same 254 default. This is NOT a 254-device capacity claim.
target_compile_definitions(m7_powerlink_passive_mn PRIVATE NMT_MAX_NODE_ID=254)
# Public oplk.h does NOT load oplkcfg/defaultcfg. In particular the upstream
# OD generator otherwise silently omits CFM/PDO/ASnd objects. Use precisely
# the core's configuration before any public structure/table is compiled.
target_compile_options(m7_powerlink_passive_mn PRIVATE -include common/oplkinc.h)
target_compile_options(m7_powerlink_passive_mn PRIVATE
    -Wall -Wextra -Werror -fno-strict-aliasing -ffunction-sections -fdata-sections)
set_target_properties(m7_powerlink_passive_mn PROPERTIES C_STANDARD 99 C_STANDARD_REQUIRED YES)
if(NOT CMAKE_CROSSCOMPILING)
    enable_testing()
    target_compile_definitions(m7_powerlink_passive_mn PRIVATE M7_EDRV_NATIVE_TEST)
    add_executable(test_powerlink_passive_mn "${port}/../../../tests/test_powerlink_passive_mn.c")
    target_link_libraries(test_powerlink_passive_mn PRIVATE
        "-Wl,--start-group" m7_powerlink_passive_mn m7_powerlink_mn_core "-Wl,--end-group")
    # Stable callsite addresses make injected allocation failures diagnosable.
    target_link_options(test_powerlink_passive_mn PRIVATE -no-pie -Wl,--wrap=malloc,--wrap=calloc,--wrap=free)
    target_compile_options(test_powerlink_passive_mn PRIVATE -UNDEBUG -Wall -Wextra -Werror)
    target_compile_options(test_powerlink_passive_mn PRIVATE -include common/oplkinc.h)
    foreach(test passive owner cdc target_failure timer_failure phy_failure sem_failure stop_failure timer_stop_failure)
        add_test(NAME mn_${test} COMMAND test_powerlink_passive_mn ${test})
    endforeach()
    # One complete passive create currently allocates 16 blocks. Fail EVERY
    # position in a fresh process; partial init must be terminal, not retried.
    foreach(position RANGE 1 16)
        add_test(NAME mn_allocation_failure_${position}
            COMMAND test_powerlink_passive_mn allocation_failure_${position})
    endforeach()
endif()

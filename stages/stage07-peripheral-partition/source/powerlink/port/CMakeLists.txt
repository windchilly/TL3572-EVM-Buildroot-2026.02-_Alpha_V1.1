cmake_minimum_required(VERSION 3.16)
project(m7_powerlink_mn_core C)
if(NOT EXISTS "${OPLK_SOURCE}/stack/include/oplk/targetsystem.h")
    message(FATAL_ERROR "Set OPLK_SOURCE to the prepared, pinned upstream tree")
endif()
set(OPLK_BASE_DIR "${OPLK_SOURCE}")
set(OPLK_STACK_DIR "${OPLK_SOURCE}/stack")
include("${OPLK_STACK_DIR}/cmake/directories.cmake")
include("${OPLK_STACK_DIR}/cmake/stackfiles.cmake")

# Both logical layers live on UP2. No pcap, sockets, Linux ioctl or dual-CPU CAL.
set(core_sources
    ${USER_SOURCES} ${USER_MN_SOURCES}
    ${CTRL_UCAL_DIRECT_SOURCES} ${DLL_UCAL_CIRCBUF_SOURCES}
    ${ERRHND_UCAL_LOCAL_SOURCES} ${EVENT_UCAL_NOOSKERNEL_SOURCES}
    ${PDO_UCAL_LOCAL_SOURCES} ${USER_TIMER_GENERIC_SOURCES}
    ${KERNEL_SOURCES} ${CTRL_KCAL_DIRECT_SOURCES}
    ${DLL_KCAL_CIRCBUF_SOURCES} ${ERRHND_KCAL_LOCAL_SOURCES}
    ${EVENT_KCAL_NOOSKERNEL_SOURCES} ${PDO_KCAL_LOCAL_SOURCES}
    ${COMMON_SOURCES} ${CIRCBUF_NOOS_SOURCES} ${MEMMAP_NULL_SOURCES}
    ${ARCH_LE_SOURCES} ${EDRV_SOURCE_DIR}/edrvcyclic.c)
add_library(m7_powerlink_mn_core STATIC ${core_sources})
target_include_directories(m7_powerlink_mn_core PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}" "${STACK_INCLUDE_DIR}"
    "${STACK_SOURCE_DIR}" "${CONTRIB_SOURCE_DIR}")
target_compile_definitions(m7_powerlink_mn_core PUBLIC
    OPLK_TARGET_UNIPROTON CONFIG_MN NDEBUG)
target_compile_options(m7_powerlink_mn_core PRIVATE
    -Wall -Wextra -Werror=implicit-function-declaration -Werror=incompatible-pointer-types
    -Werror=int-conversion -Werror=return-type
    -fno-strict-aliasing -ffunction-sections -fdata-sections)
set_target_properties(m7_powerlink_mn_core PROPERTIES C_STANDARD 99 C_STANDARD_REQUIRED YES)
if(CMAKE_SYSTEM_PROCESSOR STREQUAL "aarch64")
    target_compile_options(m7_powerlink_mn_core PUBLIC
        -mcpu=cortex-a53 -mgeneral-regs-only -mstrict-align -mno-outline-atomics)
endif()

if(NOT CMAKE_CROSSCOMPILING)
    enable_testing()
    add_executable(test_powerlink_mn_core "${CMAKE_CURRENT_SOURCE_DIR}/../../../tests/test_powerlink_mn_core.c")
    target_link_libraries(test_powerlink_mn_core PRIVATE m7_powerlink_mn_core)
    # Keep assert checks active even with a Release core build.
    target_compile_options(test_powerlink_mn_core PRIVATE -UNDEBUG -Wall -Wextra -Werror)
    add_test(NAME mn_state_and_ami COMMAND test_powerlink_mn_core)
    add_executable(test_powerlink_od "${CMAKE_CURRENT_SOURCE_DIR}/../../../tests/test_powerlink_od.c")
    target_link_libraries(test_powerlink_od PRIVATE m7_powerlink_mn_core)
    target_compile_options(test_powerlink_od PRIVATE -UNDEBUG -Wall -Wextra -Werror)
    add_test(NAME od_integer_range_and_no_fp COMMAND test_powerlink_od)
endif()

# One app, two images on nRF5340 (FW-1): the same source builds for cpuapp and cpunet.
if(NOT "${SB_CONFIG_NET_CORE_BOARD}" STREQUAL "" AND NOT TARGET fw_net)
  # #118: each OpenPack board carries one role (the pack has the PCM1840 and nRF21540, the receiver the PCM5102A).
  if(BOARD STREQUAL "openpack_pack" AND SB_CONFIG_OP_ROLE_RX)
    message(FATAL_ERROR "openpack_pack is the pack board: build the receiver for openpack_rx")
  elseif(BOARD STREQUAL "openpack_rx" AND NOT SB_CONFIG_OP_ROLE_RX)
    message(FATAL_ERROR "openpack_rx is the receiver board: SB_CONFIG_OP_ROLE_RX must stay y")
  endif()
  if(SB_CONFIG_OP_ROLE_RX AND NOT BOARD STREQUAL "openpack_rx") # openpack_rx has no FEM node to drop
    # ADR-0021: receiver = BT40E, no nRF21540. Drop the pack's FEM node from the receiver net core.
    set(rx_overlay ${CMAKE_CURRENT_LIST_DIR}/boards/role_rx_cpunet.overlay)
    if(NOT rx_overlay IN_LIST fw_net_EXTRA_DTC_OVERLAY_FILE)
      set(fw_net_EXTRA_DTC_OVERLAY_FILE ${fw_net_EXTRA_DTC_OVERLAY_FILE} ${rx_overlay}
          CACHE INTERNAL "receiver net core: no FEM (ADR-0021)" FORCE)
    endif()
  endif()
  ExternalZephyrProject_Add(
    APPLICATION fw_net
    SOURCE_DIR  ${APP_DIR}
    BOARD       ${SB_CONFIG_NET_CORE_BOARD}
  )
  if(SB_CONFIG_OP_ROLE_RX)
    set_config_bool(${DEFAULT_IMAGE} CONFIG_OP_ROLE_RX y)
    set_config_bool(fw_net CONFIG_OP_ROLE_RX y)
  endif()
  if(SB_CONFIG_OP_TIME_DIVERSITY)
    set_config_bool(${DEFAULT_IMAGE} CONFIG_OP_TIME_DIVERSITY y)
    set_config_bool(fw_net CONFIG_OP_TIME_DIVERSITY y)
  endif()
  if(BOARD STREQUAL "nrf5340bsim")
    native_simulator_set_child_images(${DEFAULT_IMAGE} fw_net)
    native_simulator_set_final_executable(${DEFAULT_IMAGE})
  endif()
endif()

# The pack board has no BOOT strap (the receiver has one: BP_BOOT, ADR-0014): MCUboot serial recovery is entered by the
# app's `dfu` command only (#25). Without a strap pin MCUboot's GPIO entrance does not compile.
if(BOARD STREQUAL "openpack_pack" AND SB_CONFIG_BOOTLOADER_MCUBOOT)
  set_config_bool(mcuboot CONFIG_BOOT_SERIAL_ENTRANCE_GPIO n)
  set(cdc_overlay ${CMAKE_CURRENT_LIST_DIR}/sysbuild/mcuboot_cdc.overlay)
  if(NOT cdc_overlay IN_LIST mcuboot_EXTRA_DTC_OVERLAY_FILE)
    set(mcuboot_EXTRA_DTC_OVERLAY_FILE ${mcuboot_EXTRA_DTC_OVERLAY_FILE} ${cdc_overlay}
        CACHE INTERNAL "pack: MCUboot serial recovery on USB CDC ACM" FORCE)
  endif()
  set_config_bool(mcuboot CONFIG_BOOT_SERIAL_UART n)
  set_config_bool(mcuboot CONFIG_BOOT_SERIAL_CDC_ACM y)
endif()

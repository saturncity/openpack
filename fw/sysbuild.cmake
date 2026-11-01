# One app, two images on nRF5340 (FW-1): the same source builds for cpuapp and cpunet.
if(NOT "${SB_CONFIG_NET_CORE_BOARD}" STREQUAL "" AND NOT TARGET fw_net)
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

# Receiver role (RX-2..RX-5): net core acquires, tracks and merges; app core consumes merged frames.
target_include_directories(app PRIVATE ${CMAKE_CURRENT_LIST_DIR})
if(CONFIG_OP_NRF5340 AND CONFIG_OP_ROLE_RX)
  if(CONFIG_SOC_COMPATIBLE_NRF5340_CPUNET)
    target_sources(app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/rx.c ${CMAKE_CURRENT_LIST_DIR}/ant.c)
  else()
    target_sources(app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../rx_app/rx_app.c)
  endif()
endif()

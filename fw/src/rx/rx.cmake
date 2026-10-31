# Receiver role (RX-2..RX-7): net core acquires, tracks and merges; app core decodes, conceals,
# buffers and clocks out (rx_app, clk).
target_include_directories(app PRIVATE ${CMAKE_CURRENT_LIST_DIR})
if(CONFIG_OP_NRF5340 AND CONFIG_OP_ROLE_RX)
  if(CONFIG_SOC_COMPATIBLE_NRF5340_CPUNET)
    target_sources(app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/rx.c ${CMAKE_CURRENT_LIST_DIR}/ant.c)
  else()
    set(OP_FW ${CMAKE_CURRENT_LIST_DIR}/../..)
    target_sources(app PRIVATE
      ${OP_FW}/src/rx_app/rx_app.c ${OP_FW}/src/rx_app/op_jslot.c ${OP_FW}/src/rx_app/op_plc.c
      ${OP_FW}/src/clk/op_clk.c ${OP_FW}/src/clk/op_aclk.c ${OP_FW}/codec/adpcm6.c)
    target_include_directories(app PRIVATE ${OP_FW}/src/rx_app ${OP_FW}/src/clk ${OP_FW}/codec)
  endif()
endif()

# Audio I/O (FW-3). Included from fw/CMakeLists.txt and the audio test.
set(OP_AUDIO_DIR ${CMAKE_CURRENT_LIST_DIR})
target_include_directories(app PRIVATE ${OP_AUDIO_DIR}/../../include ${OP_AUDIO_DIR})
if(CONFIG_OP_AUDIO_WAV)
  target_sources(app PRIVATE ${OP_AUDIO_DIR}/op_audio_wav.c)
  target_sources(native_simulator INTERFACE ${OP_AUDIO_DIR}/op_wav_host_bottom.c)
else()
  target_sources(app PRIVATE ${OP_AUDIO_DIR}/op_audio_i2s.c ${OP_AUDIO_DIR}/op_i2s_ring.c)
endif()

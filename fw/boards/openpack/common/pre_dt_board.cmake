# As the nRF5340 DK: the SoC dtsi has overlapping unit addresses (flash-controller/kmu, clock/power, image/image_s).
list(APPEND EXTRA_DTC_FLAGS "-Wno-unique_unit_address_if_enabled")

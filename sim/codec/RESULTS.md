# Codec bake-off (#13)

21 clips (10 VCTK 0.92, 10 VocalSet 1.1, 1 synthetic whisper->scream sweep), 48 kHz, first 6 s after leading silence, peak-normalised to -3.0 dBFS ("0 dB") and again at -20 dB. Reference = unquantised float input; degraded = codec output (frames of 48 samples, no loss). `pcm16` = plain 16-bit rounding (ceiling for any 16-bit codec input). ViSQOL v3.3.3 audio mode 48 kHz (MOS-LQO); PESQ WB after 16 kHz resample (secondary). Regenerate: `sim/codec/bakeoff.py`.

| level | codec | B/frame | ViSQOL mean | ViSQOL worst (clip) | PESQ-WB mean | PESQ-WB worst |
|---|---|---|---|---|---|---|
| 0 dB | pcm16 | - | 4.73 | 4.73 (vs_f3_long_forte_a.wav) | 4.64 | 4.64 |
| 0 dB | adpcm6 | 39 | 4.60 | 4.20 (vs_m2_scales_belt_a.wav) | 4.56 | 4.39 |
| 0 dB | adpcm8 | 51 | 4.62 | 4.34 (vs_m2_scales_belt_a.wav) | 4.57 | 4.45 |
| 0 dB | bf8_3 | 51 | 4.62 | 4.27 (vs_f3_long_forte_a.wav) | 4.62 | 4.57 |
| -20 dB | pcm16 | - | 4.73 | 4.73 (vs_m5_long_forte_a.wav) | 4.64 | 4.61 |
| -20 dB | adpcm6 | 39 | 4.61 | 4.29 (vs_f1_scales_belt_a.wav) | 4.55 | 4.36 |
| -20 dB | adpcm8 | 51 | 4.65 | 4.46 (vs_f1_scales_belt_a.wav) | 4.57 | 4.43 |
| -20 dB | bf8_3 | 51 | 4.65 | 4.50 (vs_m5_long_forte_a.wav) | 4.59 | 4.38 |

Per-clip scores: `results.csv`. Clips used:

- `vctk_p225_001_mic1.flac`
- `vctk_p228_004_mic1.flac`
- `vctk_p233_007_mic1.flac`
- `vctk_p236_010_mic1.flac`
- `vctk_p240_012_mic1.flac`
- `vctk_p243_003_mic1.flac`
- `vctk_p226_008_mic1.flac`
- `vctk_p229_002_mic1.flac`
- `vctk_p232_005_mic1.flac`
- `vctk_p241_006_mic1.flac`
- `vs_f1_scales_belt_a.wav`
- `vs_m2_scales_belt_a.wav`
- `vs_f3_long_forte_a.wav`
- `vs_m5_long_forte_a.wav`
- `vs_f2_long_pp_a.wav`
- `vs_m3_arpeggios_vibrato_a.wav`
- `vs_f4_scales_vocal_fry_a.wav`
- `vs_m6_arpeggios_breathy_a.wav`
- `vs_f5_scales_straight_a.wav`
- `vs_m9_row_spoken.wav`
- `synthetic_sweep`

## Decision input

Every codec's worst clip is above the SYS-4 floor of 4.0 at both levels (adpcm6 worst 4.20 at 0 dB, 4.29 at -20 dB). The three means sit within 0.05 of each other and 0.13 of the 16-bit ceiling, so the choice is by bytes, not quality: see `docs/adr/0005-codec.md`. A/B clips (first two VCTK, first VocalSet and sweep, each codec) are written to `sim/.cache/ab/` for the human.

## ViSQOL build (macOS, Apple clang, for repeatability)

google/visqol v3.3.3 with `USE_BAZEL_VERSION=5.1.0 BAZEL_USE_CPP_ONLY_TOOLCHAIN=1 bazelisk build :visqol -c opt` (the stock Bazel 5 cc wrapper lacks LC_UUID and dies under current dyld). Patches needed: Armadillo 9.860.2 URL is dead (use 12.6.7, update sha256 in `WORKSPACE`); zlib 1.2.11 `zutil.h` defines `fdopen` as NULL on macOS (rename that macro); TensorFlow Lite `elementwise.cc:228` needs `std::abs<float>` replaced by a lambda. Model: `--similarity_to_quality_model visqol_src/model/libsvm_nu_svr_model.txt` (`quality.py` passes it).

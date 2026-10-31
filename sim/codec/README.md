# sim/codec

Reference codecs (ADPCM-6, ADPCM-8, block-float 8+3) for #12. `from sim.codec.codec import CODECS` -> `{name: (encode, decode)}`; `encode(int16[48]) -> bytes`, `decode(bytes) -> int16[48]`. Frame bytes incl. 3 B codec_state: adpcm6 39, adpcm8 51, bf8_3 51 (format in `codec.py` docstring).

Golden vectors (`golden/`, regenerate with `python3 sim/codec/gen_golden.py`): `pcm_in.bin` = N frames of 48 little-endian int16 (silence, full-scale alternating, 30 sweep frames); `<codec>_enc.bin` = encoded frames concatenated (fixed size per codec); `<codec>_dec.bin` = decoded PCM, same layout as `pcm_in.bin`. FW-4 C must match `_enc` and `_dec` bit-exactly.

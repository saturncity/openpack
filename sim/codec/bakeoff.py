"""Codec bake-off (#13): ViSQOL + PESQ-WB of each codec vs the unquantised input. Needs sim/.cache/venv (numpy scipy soundfile pesq
remotezip) + the ViSQOL binary (see quality.py). Run: sim/.cache/venv/bin/python sim/codec/bakeoff.py  -> RESULTS.md, sim/.cache/ab/*.wav
Corpus is fetched by HTTP range from the VCTK 0.92 (Edinburgh) and VocalSet 1.2 (Zenodo) zips into sim/.cache/corpus (gitignored)."""
import io, json, os, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
import codec
import quality

CACHE = os.path.join(HERE, "..", ".cache")
VCTK = "https://datashare.ed.ac.uk/bitstream/handle/10283/3443/VCTK-Corpus-0.92.zip?sequence=2&isAllowed=y"
VOCALSET = "https://zenodo.org/api/records/1442513/files/VocalSet1-2.zip/content"
# 6 female + 4 male VCTK speakers, 1 utterance each
VCTK_FILES = [f"wav48_silence_trimmed/p{s}/p{s}_{u:03d}_mic1.flac" for s, u in
              [(225, 1), (228, 4), (233, 7), (236, 10), (240, 12), (243, 3), (226, 8), (229, 2), (232, 5), (241, 6)]]
# singer/technique path fragments (first .wav match each): loud (belt, forte), soft (pp), plus colour techniques
VOCALSET_PICK = ["female1/scales/belt/", "male2/scales/belt/", "female3/long_tones/forte/", "male5/long_tones/forte/",
                 "female2/long_tones/pp/", "male3/arpeggios/vibrato/", "female4/scales/vocal_fry/",
                 "male6/arpeggios/breathy/", "female5/scales/straight/", "male9/excerpts/"]
SECS = 6.0
PEAK_DB = -3.0  # clips peak-normalised to this, then scored again at -20 dB further down


def fetch():
    import remotezip

    def RemoteZip(url):  # the servers drop long range reads now and then
        for i in range(8):
            try: return remotezip.RemoteZip(url)
            except Exception as e: print("retry", e.__class__.__name__, flush=True)
        raise RuntimeError(url)

    out = []
    for url, names in ((VCTK, VCTK_FILES), (VOCALSET, None)):
        d = os.path.join(CACHE, "corpus"); os.makedirs(d, exist_ok=True)
        z = None
        if names is None:
            z = RemoteZip(url); allw = [n for n in z.namelist() if n.endswith(".wav") and not n.startswith("__")]; allw.sort()
            names = [next(n for n in allw if f"data_by_singer/{p}" in n) for p in VOCALSET_PICK]
        for n in names:
            f = os.path.join(d, ("vctk_" if "flac" in n else "vs_") + os.path.basename(n))
            if not os.path.exists(f):
                z = z or RemoteZip(url)
                open(f, "wb").write(z.read(n))
            out.append(f)
    return out


def prep(path):
    x, fs = sf.read(path, dtype="float64")
    if x.ndim > 1: x = x.mean(1)
    if fs != 48000:
        from math import gcd
        g = gcd(48000, fs); x = resample_poly(x, 48000 // g, fs // g)
    i = int(np.argmax(np.abs(x) > 0.02 * np.abs(x).max()))  # skip leading silence
    x = x[i:i + int(SECS * 48000)]
    return x / np.abs(x).max() * 10 ** (PEAK_DB / 20)


def run_codec(x, name):
    enc, dec = codec.CODECS[name]
    q = np.clip(np.round(x * 32768), -32768, 32767).astype(np.int16)
    q = np.pad(q, (0, -len(q) % codec.N)).reshape(-1, codec.N)
    return np.concatenate([dec(enc(f)) for f in q])[:len(x)]


def main():
    clips = {os.path.basename(f): prep(f) for f in fetch()}
    s = codec.test_signal(int(SECS * 1000)).ravel().astype(np.float64) / 32768
    clips["synthetic_sweep"] = s / np.abs(s).max() * 10 ** (PEAK_DB / 20)
    names = ["pcm16"] + list(codec.CODECS)
    res = {}  # (level, codec) -> {clip: (visqol, pesq)}
    os.makedirs(os.path.join(CACHE, "ab"), exist_ok=True)
    for lvl in (0, -20):
        for c, x in clips.items():
            ref = x * 10 ** (lvl / 20)
            for n in names:
                deg = np.clip(np.round(ref * 32768), -32768, 32767) / 32768 if n == "pcm16" else run_codec(ref, n) / 32768
                res.setdefault(f"{lvl}|{n}", {})[c] = (quality.visqol(ref, deg), quality.pesq_wb(ref, deg))
                print(lvl, c, n, res[f"{lvl}|{n}"][c], flush=True)
                if lvl == 0 and n != "pcm16" and c in list(clips)[:2] + ["synthetic_sweep"]:
                    sf.write(os.path.join(CACHE, "ab", f"{c}.{n}.wav"), deg, 48000, subtype="PCM_16")
    with open(os.path.join(CACHE, "results.csv"), "w") as f:
        f.write("level_db,codec,clip,visqol,pesq_wb\n")
        for k, r in res.items():
            for c, (v, p) in r.items():
                f.write(f"{k.replace('|', ',')},{c},{v:.3f},{p:.3f}\n")
    write_md(res, clips)


def write_md(res, clips):
    L = ["# Codec bake-off (#13)", "",
         f"{len(clips)} clips (10 VCTK 0.92, 10 VocalSet 1.2, 1 synthetic whisper->scream sweep), 48 kHz, first {SECS:.0f} s after leading silence, "
         f"peak-normalised to {PEAK_DB} dBFS (\"0 dB\") and again at -20 dB. Reference = unquantised float input; degraded = codec output "
         "(frames of 48 samples, no loss). `pcm16` = plain 16-bit rounding (ceiling for any 16-bit codec input). "
         "ViSQOL v3.3.3 audio mode 48 kHz (MOS-LQO); PESQ WB after 16 kHz resample (secondary). Regenerate: `sim/codec/bakeoff.py`.", "",
         "| level | codec | B/frame | ViSQOL mean | ViSQOL worst (clip) | PESQ-WB mean | PESQ-WB worst |", "|---|---|---|---|---|---|---|"]
    for lvl in (0, -20):
        for n in ["pcm16"] + list(codec.CODECS):
            r = res[f"{lvl}|{n}"]; v = {c: a for c, (a, b) in r.items()}; p = [b for a, b in r.values()]
            w = min(v, key=v.get)
            L.append(f"| {lvl} dB | {n} | {codec.FRAME_BYTES.get(n, '-')} | {np.mean(list(v.values())):.2f} | {v[w]:.2f} ({w}) | {np.mean(p):.2f} | {min(p):.2f} |")
    L += ["", "Per-clip scores: `results.csv` in the `bakeoff` workflow artifact. Clips used:", ""] + [f"- `{c}`" for c in clips]
    open(os.path.join(HERE, "RESULTS.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()

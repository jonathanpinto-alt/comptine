#!/usr/bin/env python3
"""Cale les paroles du bain sur une chanson fournie → assets/bain/son/alignement.json.

    python outils/aligner_son.py [--chanson bain|toc] [--modeles DOSSIER]

1. Isole la voix avec Spleeter (sherpa-onnx, modèle « sherpa-onnx-spleeter-2stems-fp16 »
   téléchargé depuis les releases GitHub de k2-fsa/sherpa-onnx).
2. Calcule la force d'attaque de la voix (librosa) toutes les 10 ms.
3. Pour chaque passage chanté de comptine/bain/son.py (BLOCS), place les N syllabes
   des lignes du passage par programmation dynamique : chaque syllabe tombe sur une
   attaque, avec des écarts réguliers (pénalité sur le logarithme de l'écart).
À lancer une fois quand la chanson change (pip install sherpa-onnx librosa).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib  # noqa: E402

URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/source-separation-models/"
PAS = 0.01


def modele_spleeter(dossier):
    d = Path(dossier) / "sherpa-onnx-spleeter-2stems-fp16"
    if not d.exists():
        Path(dossier).mkdir(parents=True, exist_ok=True)
        arch = Path(dossier) / "spleeter.tar.bz2"
        subprocess.run(["curl", "-sSL", "--fail", "-o", str(arch), URL + "sherpa-onnx-spleeter-2stems-fp16.tar.bz2"],
                       check=True)
        subprocess.run(["tar", "xjf", str(arch), "-C", str(dossier)], check=True)
    return d


def voix_isolee(audio, dossier_modeles):
    import sherpa_onnx as so
    import soundfile as sf
    d = modele_spleeter(dossier_modeles)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio), "-map", "0:a", "-ar", "44100", "-ac", "2",
                        str(wav)], check=True)
        x, sr = sf.read(wav, dtype="float32")
    cfg = so.OfflineSourceSeparationConfig(model=so.OfflineSourceSeparationModelConfig(
        spleeter=so.OfflineSourceSeparationSpleeterModelConfig(vocals=str(d / "vocals.fp16.onnx"),
                                                               accompaniment=str(d / "accompaniment.fp16.onnx")),
        num_threads=4))
    out = so.OfflineSourceSeparation(cfg).process(sr, np.ascontiguousarray(x.T))
    v = np.array(out.stems[0].data).mean(axis=0)
    return v, out.sample_rate


def attaques(v, sr):
    import librosa
    hop = int(sr * PAS)
    o = librosa.onset.onset_strength(y=v, sr=sr, hop_length=hop, aggregate=np.median, lag=2)
    rms = librosa.feature.rms(y=v, frame_length=4 * hop, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-7)
    hausse = np.clip(np.diff(db, prepend=db[0]), 0, None)
    n = min(len(o), len(hausse))
    f = o[:n] / (np.percentile(o, 99) + 1e-9) + 0.5 * hausse[:n] / (np.percentile(hausse, 99) + 1e-9)
    return np.clip(f, 0, 1.5), db[:n]


def aligner(force, debut, fin, n, lam=0.6, gmin=0.09, gmax=1.6):
    """Instants (s) de n syllabes dans [debut, fin] : max Σ force − λ Σ log²(écart / écart moyen)."""
    i0, i1 = int(debut / PAS), int(fin / PAS)
    f = force[i0:i1]
    T = len(f)
    moy = (fin - debut - 0.25) / max(n, 1)
    lo, hi = int(gmin / PAS), int(gmax / PAS)
    NEG = -1e18
    score = np.full((n, T), NEG)
    prec = np.zeros((n, T), dtype=int)
    score[0, : min(T, int(0.3 / PAS))] = f[: min(T, int(0.3 / PAS))]      # 1re syllabe près du début
    gaps = np.arange(lo, hi + 1)
    pen = lam * np.log(gaps * PAS / moy) ** 2
    for k in range(1, n):
        for t in range(T):
            a = t - gaps
            ok = a >= 0
            if not ok.any():
                continue
            cand = score[k - 1, a[ok]] - pen[ok]
            j = int(np.argmax(cand))
            if cand[j] > NEG / 2:
                score[k, t] = cand[j] + f[t]
                prec[k, t] = a[ok][j]
    fin_min = max(0, T - int(1.8 / PAS))                                  # dernière syllabe pas trop tôt
    t = fin_min + int(np.argmax(score[n - 1, fin_min:]))
    res = [t]
    for k in range(n - 1, 0, -1):
        t = prec[k, t]
        res.append(t)
    return [debut + x * PAS for x in reversed(res)]


def fins_syllabes(temps, fin_bloc, db, coupures):
    """Fin de chaque syllabe : début de la suivante (sauf en fin de ligne : fin de la voix)."""
    res = []
    for k, t in enumerate(temps):
        if k + 1 < len(temps) and k not in coupures:
            res.append(temps[k + 1])
        else:
            suivant = temps[k + 1] if k + 1 < len(temps) else fin_bloc
            # fin de la voix : dernier instant au-dessus du seuil avant la ligne suivante
            i0, i1 = int(t / PAS), int(suivant / PAS)
            seg = db[i0:i1]
            seuil = np.max(seg) - 20 if len(seg) else 0
            voix = np.flatnonzero(seg > seuil)
            res.append(min(suivant, t + max(0.25, (voix[-1] + 1) * PAS if len(voix) else 0.4)))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modeles", default="/tmp/modeles_sherpa")
    ap.add_argument("--chanson", choices=["bain", "toc"], default="bain")
    args = ap.parse_args()
    S = importlib.import_module(f"comptine.{args.chanson}.son")
    print("▶ voix isolée (Spleeter)…", flush=True)
    v, sr = voix_isolee(S.AUDIO, args.modeles)
    force, db = attaques(v, sr)
    sortie = []
    for debut, fin, cles in S.BLOCS:
        syls_par_ligne = [len(S.syllabes_ligne(S.texte(c))[1]) for c in cles]
        n = sum(syls_par_ligne)
        temps = aligner(force, debut, fin, n)
        coupures, acc = set(), 0
        for m in syls_par_ligne:
            acc += m
            coupures.add(acc - 1)
        fins = fins_syllabes(temps, fin, db, coupures)
        k = 0
        for c, m in zip(cles, syls_par_ligne):
            sortie.append(dict(cle=c, texte=S.texte(c),
                               syllabes=[[round(temps[k + j], 3), round(fins[k + j], 3)] for j in range(m)]))
            print(f"{temps[k]:7.2f}  {S.texte(c)}")
            k += m
    S.ALIGNEMENT.write_text(json.dumps(dict(audio=S.AUDIO.name, lignes=sortie), ensure_ascii=False, indent=1),
                            encoding="utf-8")
    print(f"✓ {S.ALIGNEMENT}")


if __name__ == "__main__":
    main()

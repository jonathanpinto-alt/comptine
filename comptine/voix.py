"""Voix chantée : espeak-ng (phonétisation) + MBROLA (synthèse).

Chaque syllabe reçoit une note de la mélodie et une durée exacte sur la grille
rythmique. On écrit un fichier .pho MBROLA (phonème, durée, points de hauteur)
pour toute la chanson : la voix « chante » donc réellement la mélodie et le
calage temporel est exact, ce qui permet un karaoké mot par mot précis.
"""
import functools
import re
import shutil
import subprocess
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf
from scipy import signal

from . import config as C
from .chanson import construire_lignes

VOIX_ESPEAK = "mb-fr4"
VOIX_MBROLA = ["/usr/share/mbrola/fr4/fr4", "/usr/lib/x86_64-linux-gnu/mbrola/fr4/fr4",
               "/usr/share/mbrola/voices/fr4"]
VOYELLES = {"a", "A", "e", "E", "i", "o", "O", "u", "y", "2", "9", "@",
            "a~", "e~", "o~", "9~"}
SONORES = VOYELLES | {"b", "d", "g", "v", "z", "Z", "m", "n", "N", "l", "R", "j", "w", "H"}
PONCT = "«»…!?,.;: \""

# liaisons simples : mot -> consonne ajoutée devant le mot suivant s'il commence par une voyelle
LIAISONS = {"les": "z", "des": "z", "aux": "z", "tout": "t", "petit": "t",
            "un": "n", "on": "n", "ils": "z", "deux": "z", "trois": "z"}


@dataclass
class Syllabe:
    attaque: list            # [(phonème, durée_ms)]
    noyau: tuple             # (voyelle, durée_ms)
    coda: list
    mot: int                 # index du mot (dans la ligne)
    fin_mot: bool = False
    debut: float = 0.0       # instant de la voyelle (s, grille)
    fin: float = 0.0
    midi: int = 60


@dataclass
class Mot:
    texte: str
    debut: float = 0.0
    fin: float = 0.0
    syllabes: list = field(default_factory=list)


# --------------------------------------------------------------------------
def verifier_outils():
    for prog in ("espeak-ng", "mbrola"):
        if not shutil.which(prog):
            raise SystemExit(f"Programme manquant : {prog} (voir README, apt install espeak-ng mbrola mbrola-fr4)")
    if not any(__import__("os").path.exists(p) for p in VOIX_MBROLA):
        raise SystemExit("Voix MBROLA fr4 introuvable (apt install mbrola-fr4)")


def base_mbrola():
    import os
    for p in VOIX_MBROLA:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("voix mbrola fr4")


@functools.lru_cache(maxsize=None)
def phonemiser(mot):
    """Phonèmes MBROLA d'un mot isolé : [(phonème, durée_ms)]."""
    propre = re.sub(r"[-]", " ", mot).replace("’", "'")
    out = subprocess.run(["espeak-ng", "-v", VOIX_ESPEAK, "-q", "--pho", propre],
                         capture_output=True, text=True, check=True).stdout
    res = []
    for ligne in out.splitlines():
        champs = ligne.split()
        if len(champs) < 2 or champs[0] == "_":
            continue
        res.append((champs[0], int(champs[1])))
    return res


def decouper_mots(texte):
    """Découpe la ligne en mots affichables (la ponctuation reste collée)."""
    jetons = texte.replace(" ", " ").split()
    mots = []
    attente = ""
    for j in jetons:
        if not j.strip(PONCT):            # ponctuation seule : « ou »
            if j in ("«",):
                attente += j + " "
            elif mots:
                mots[-1] += " " + j
            continue
        mots.append(attente + j)
        attente = ""
    return mots


def nettoyer(mot):
    return mot.replace(" ", " ").strip(PONCT + " ").lower()


def syllaber(phones, idx_mot):
    syl = []
    attaque = []
    for ph, d in phones:
        if ph in VOYELLES:
            syl.append(Syllabe(attaque, (ph, d), [], idx_mot))
            attaque = []
        else:
            attaque.append((ph, d))
    if attaque:
        if syl:
            syl[-1].coda.extend(attaque)
        else:   # mot sans voyelle (rare) : on invente un schwa
            syl.append(Syllabe(attaque, ("@", 80), [], idx_mot))
    if syl:
        syl[-1].fin_mot = True
    # dans un mot, les consonnes entre deux voyelles vont dans l'attaque suivante,
    # sauf la première d'un groupe de 2+ (ex. « par-tir ») qui ferme la syllabe
    for a, b in zip(syl, syl[1:]):
        if len(b.attaque) >= 2 and b.attaque[0][0] in ("R", "l", "s") and b.attaque[1][0] not in ("j", "w", "H"):
            a.coda.append(b.attaque.pop(0))
    return syl


def rythme(syls, slots):
    """Durées (en doubles croches) de chaque syllabe pour remplir `slots`."""
    n = len(syls)
    d = [2] * n
    reste = slots - 2 * n
    if reste >= 0:
        bonus = min(reste, 4)
        d[-1] += bonus
        reste -= bonus
        cand = [i for i in range(n - 1) if syls[i].fin_mot]
        k = min(reste // 2, len(cand))
        if k:
            choix = [cand[round(j * (len(cand) - 1) / max(k - 1, 1))] for j in range(k)] if k > 1 else [cand[0]]
            for i in sorted(set(choix)):
                d[i] += 2
                reste -= 2
        d[-1] += reste
    else:
        manque = -reste
        ordre = [i for i in range(n - 1) if not syls[i].fin_mot] + \
                [i for i in range(n - 1) if syls[i].fin_mot]
        for i in ordre[:manque]:
            d[i] = 1
        manque -= min(manque, len(ordre))
        if manque:
            raise ValueError(f"ligne trop longue pour {slots} doubles croches")
    return d


def preparer_lignes(construire=construire_lignes):
    """Construit les lignes avec mots, syllabes, notes et timings (grille).

    Une ligne peut imposer ses durées (`durees`, en doubles croches) et ses notes
    (`notes`, une par syllabe) ; sinon le rythme est réparti automatiquement et
    les notes sont piochées dans le gabarit."""
    lignes = construire()
    for L in lignes:
        mots_txt = decouper_mots(L.texte)
        cles = [nettoyer(m) for m in mots_txt]
        mots = []
        syls = []
        for i, (m, cle) in enumerate(zip(mots_txt, cles)):
            ph = list(phonemiser(cle))
            if i > 0 and cles[i - 1] in LIAISONS and ph and ph[0][0] in VOYELLES \
                    and not mots_txt[i - 1].rstrip().endswith((",", "!", "?", ".", "…")):
                ph.insert(0, (LIAISONS[cles[i - 1]], 60))
            s = syllaber(ph, i)
            mots.append(Mot(m, syllabes=s))
            syls.extend(s)
        for attendu, nom in ((L.durees, "durées"), (L.notes, "notes")):
            if attendu is not None and len(attendu) != len(syls):
                raise ValueError(f"« {L.texte} » : {len(syls)} syllabes, mais {len(attendu)} {nom} "
                                 f"({' '.join(s.noyau[0] for s in syls)})")
        durees = L.durees or rythme(syls, L.slots)
        t0 = (L.mesure * 16 + L.decalage) * C.DOUBLE
        pos = 0
        for k, (s, d) in enumerate(zip(syls, durees)):
            s.debut = t0 + pos * C.DOUBLE
            s.fin = s.debut + d * C.DOUBLE
            if L.notes:
                s.midi = L.notes[k] + L.transpo
            else:
                idx = min(pos // 2, len(L.gabarit) - 1)
                s.midi = L.gabarit[idx] + L.transpo
            pos += d
        for m in mots:
            m.debut = m.syllabes[0].debut
            m.fin = m.syllabes[-1].fin
        L.syllabes = syls
        L.mots = mots
    return lignes


# --------------------------------------------------------------------------
def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def segments_ligne(L):
    """Phonèmes cibles d'une ligne : [(debut_s, fin_s, phoneme, points_hauteur, duree_espeak_ms)]."""
    seg = []
    syls = L.syllabes
    for k, s in enumerate(syls):
        f = hz(s.midi)
        # attaque : placée AVANT le temps pour que la voyelle tombe pile sur la note
        att = [(p, min(d, 75) / 1000, d) for p, d in s.attaque]
        tot = sum(d for _, d, _ in att)
        dispo = (s.fin - s.debut) * 0.35
        if k > 0:
            dispo = min(dispo, (syls[k - 1].fin - syls[k - 1].debut) * 0.45)
        if tot > dispo:
            att = [(p, d * dispo / tot, o) for p, d, o in att]
            tot = dispo
        s.t_son = s.debut - tot
        s.att = att
        s.f = f
    for k, s in enumerate(syls):
        legato = k + 1 < len(syls)
        fin_son = syls[k + 1].t_son if legato else s.fin - 0.06
        coda = [(p, min(d, 70) / 1000, d) for p, d in s.coda]
        totc = sum(d for _, d, _ in coda)
        dispo = max(0.0, (fin_son - s.debut) - 0.05)
        if totc > dispo * 0.5:
            coda = [(p, d * dispo * 0.5 / totc, o) for p, d, o in coda]
            totc = dispo * 0.5
        t = s.t_son
        for p, d, o in s.att:
            seg.append((t, t + d, p, [(50, s.f)], o))
            t += d
        fin_v = fin_son - totc
        dv = fin_v - t
        f_prec = syls[k - 1].f if k > 0 else s.f * 0.96
        pts = [(0, f_prec), (15, s.f)]
        if dv > 0.33:
            for pc, r in ((40, 1.0), (52, 1.012), (64, 0.988), (76, 1.014), (88, 0.986), (100, 1.0)):
                pts.append((pc, s.f * r))
        else:
            pts.append((100, s.f))
        seg.append((t, fin_v, s.noyau[0], pts, s.noyau[1]))
        t = fin_v
        for p, d, o in coda:
            seg.append((t, t + d, p, [(50, s.f)], o))
            t += d
    return seg


def ecrire_pho(lignes, chemin):
    """Écrit le fichier .pho de toute la chanson (temps absolus, sans dérive)."""
    seg = []        # (debut_s, fin_s, phoneme, points_hauteur)
    for L in lignes:
        seg.extend(x[:4] for x in segments_ligne(L))

    seg.sort(key=lambda x: x[0])
    lignes_pho = []
    curseur = 0.0
    for deb, fin, p, pts in seg:
        if deb > curseur + 0.001:
            ajouter_silence(lignes_pho, curseur, deb)
            curseur = deb
        deb = max(deb, curseur)
        ms = round(fin * 1000) - round(deb * 1000)
        if ms <= 0:
            continue
        txt = " ".join(f"{pc} {fr:.0f}" for pc, fr in pts)
        lignes_pho.append(f"{p} {ms} {txt}")
        curseur = round(fin * 1000) / 1000
    ajouter_silence(lignes_pho, curseur, C.DUREE_TOTALE)
    chemin.write_text("\n".join(lignes_pho) + "\n", encoding="utf-8")


def ajouter_silence(lignes_pho, deb, fin):
    a, b = round(deb * 1000), round(fin * 1000)
    while b - a > 0:
        d = min(1500, b - a)
        lignes_pho.append(f"_ {d}")
        a += d


def reverb(x, sr, duree=0.9, mix=0.18, seed=1):
    rng = np.random.default_rng(seed)
    n = int(sr * duree)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    ir = signal.lfilter([1], [1, -0.6], ir)     # adoucit les aigus
    ir /= np.sqrt(np.sum(ir ** 2))
    humide = signal.fftconvolve(x, ir)[: len(x)]
    return (1 - mix) * x + mix * humide


def synthetiser(lignes, dossier):
    """Génère voix.wav (44,1 kHz mono) et renvoie le signal."""
    verifier_outils()
    pho = dossier / "voix.pho"
    brut = dossier / "voix_mbrola.wav"
    ecrire_pho(lignes, pho)
    subprocess.run(["mbrola", "-e", base_mbrola(), str(pho), str(brut)], check=True,
                   capture_output=True)
    x, sr = sf.read(brut, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    from math import gcd
    g = gcd(C.SR, sr)
    x = signal.resample_poly(x, C.SR // g, sr // g).astype(np.float32)
    # filtre passe-haut doux + légère réverb
    b, a = signal.butter(2, 90 / (C.SR / 2), "high")
    x = signal.lfilter(b, a, x)
    x = reverb(x, C.SR)
    n = int(round(C.DUREE_TOTALE * C.SR))
    x = np.pad(x, (0, max(0, n - len(x))))[:n]
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
    sf.write(dossier / "voix.wav", x, C.SR)
    return x

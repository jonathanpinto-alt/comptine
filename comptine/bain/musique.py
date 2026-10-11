"""Accompagnement de « C'est l'heure du bain » (MIDI → FluidSynth) + bruitages.

- intro : glockenspiel et xylophone annoncent le « splash splash splash » ;
- couplets : ukulélé, basse, maracas, petites réponses de marimba ;
- refrains : piano, claps, tambourin, glockenspiel qui double la voix, puis
  2 mesures instrumentales où le xylophone rejoue le refrain ;
- fin : berceuse (boîte à musique, cordes, célesta), sans batterie ;
- outro : la boîte à musique rejoue le refrain au ralenti, accord final.
Bruitages synthétisés : bulles (« bloup »), éclaboussures, couinement du canard.
"""
import random

import numpy as np
import pretty_midi
from scipy import signal

from .. import config as C
from ..musique import (BASSE_ACOUSTIQUE, BOITE, CELESTA, CLAP, CLOCHETTE, CORDES, CRASH, GLOCK,
                       GUITARE_NYLON, HAT, KICK, MARACAS, MARIMBA, PIANO, PIPEAU, SNARE, TAMBOURIN,
                       TRIANGLE, XYLO, Piste, hauteur_accord, t)
from . import chanson as B


def composer(lignes):
    pm = pretty_midi.PrettyMIDI(initial_tempo=C.BPM)
    xylo = Piste(pm, XYLO, "Xylophone")
    glock = Piste(pm, GLOCK, "Glockenspiel")
    boite = Piste(pm, BOITE, "Boîte à musique")
    celesta = Piste(pm, CELESTA, "Célesta")
    basse = Piste(pm, BASSE_ACOUSTIQUE, "Basse")
    piano = Piste(pm, PIANO, "Piano")
    ukulele = Piste(pm, GUITARE_NYLON, "Guitare")
    cordes = Piste(pm, CORDES, "Cordes")
    flute = Piste(pm, PIPEAU, "Flûte")
    marimba = Piste(pm, MARIMBA, "Marimba")
    batt = Piste(pm, 0, "Batterie", batterie=True)

    accords = B.accords_par_mesure()
    N = len(accords)
    debut_section = {}
    for nom, typ, m0, nb, _sc, _tr in B.SECTIONS:
        for k in range(nb):
            debut_section[m0 + k] = (m0, k)

    for m, (acc, tr, typ) in enumerate(accords):
        racine = hauteur_accord(acc, tr, 36)[0]
        quinte = racine + 7
        triade = hauteur_accord(acc, tr, 60)
        triade_g = hauteur_accord(acc, tr, 55)
        m0, k_sec = debut_section[m]

        if typ in ("fin", "outro"):
            # berceuse : cordes tenues, boîte à musique en arpèges, basse ronde
            dernier = m == N - 1
            for n in triade_g:
                cordes.note(n, t(m), C.MESURE, 50 if typ == "fin" else 42)
            basse.note(racine, t(m), C.MESURE * 0.95, 58)
            if dernier:
                for n in triade + [triade[0] + 12]:
                    celesta.note(n + 12, t(m), C.MESURE, 70)
                    boite.note(n + 12, t(m, 0.5), 2.0, 60)
                batt.note(CLOCHETTE, t(m), 2.0, 60)
                continue
            arp = [triade[0] + 12, triade[1] + 12, triade[2] + 12, triade[1] + 12]
            for k in range(8):
                boite.note(arp[k % 4], t(m, k * 0.5), 0.6, 55 if typ == "fin" else 48)
            if k_sec % 2 == 0:
                batt.note(TRIANGLE, t(m), 0.5, 30)
            continue

        energie = {"intro": 1, "couplet": 1, "refrain": 2}[typ]
        pause = typ == "refrain" and k_sec >= 8          # 2 mesures instrumentales

        # basse : fondamentale / quinte en noires (rebondissante en refrain)
        if energie >= 2:
            motif = [racine, racine + 12, quinte, racine + 12]
            for k, h in enumerate(motif):
                basse.note(h, t(m, k), C.NOIRE * 0.6, 92 if k % 2 == 0 else 75)
        else:
            for k, h in enumerate([racine, quinte, racine + 12, quinte]):
                basse.note(h, t(m, k), C.NOIRE * 0.8, 88 if k % 2 == 0 else 70)

        if typ in ("couplet", "intro"):
            for k in (0.5, 1.5, 2.5, 3.5):
                for n in triade:
                    ukulele.note(n, t(m, k), C.CROCHE * 0.9, 60)
        else:
            for k in (0, 1, 1.5, 2, 3, 3.5):
                for n in triade:
                    piano.note(n, t(m, k), C.CROCHE * 0.9, 68 if k in (0, 2) else 52)
            if pause:
                for n in triade:
                    cordes.note(n, t(m), C.MESURE, 50)

        # batterie (pas de batterie dans les 2 premières mesures de l'intro)
        if typ == "intro" and m < 2:
            batt.note(TRIANGLE, t(m), 0.5, 45)
            continue
        for k in range(4):
            if k in (0, 2):
                batt.note(KICK, t(m, k), 0.2, 95 if energie > 1 else 80)
            else:
                batt.note(CLAP if energie >= 2 else SNARE, t(m, k), 0.2, 82 if energie >= 2 else 55)
            batt.note(MARACAS, t(m, k + 0.5), 0.1, 42)
        if energie >= 2:
            for k in range(8):
                batt.note(TAMBOURIN, t(m, k * 0.5), 0.1, 66 if k % 2 else 42)
        if pause:
            for k in range(8):
                batt.note(HAT, t(m, k * 0.5), 0.1, 50)

    # crash au début de chaque refrain, cloche au début de la fin
    for nom, typ, m0, nb, _sc, tr in B.SECTIONS:
        if typ == "refrain":
            batt.note(CRASH, t(m0), 1.5, 80)
        elif typ == "fin":
            batt.note(CLOCHETTE, t(m0), 1.5, 55)

    # ----------------------------------------------------------- mélodie
    for L in lignes:
        for s in L.syllabes:
            d = (s.fin - s.debut) * 0.95
            doux = L.type_section == "fin"
            flute.note(s.midi, s.debut, d, 40 if doux else 50)
            if L.type_section == "refrain":
                glock.note(s.midi + 12, s.debut, min(d, 0.6), 60)
            if doux:
                celesta.note(s.midi + 12, s.debut, min(d, 0.8), 40)

    # petites réponses de marimba dans les respirations des couplets
    for L in lignes:
        if L.type_section == "couplet":
            fin_ligne = (L.mesure + 2) * C.MESURE
            acc, tr, _ = accords[min(L.mesure + 1, N - 1)]
            tri = hauteur_accord(acc, tr, 72)
            for k, n in enumerate([tri[0], tri[1], tri[2], tri[0] + 12]):
                marimba.note(n, fin_ligne - C.NOIRE + k * C.DOUBLE, C.DOUBLE, 70)

    # le refrain rejoué : intro (2 lignes, xylophone), pauses des refrains (xylophone),
    # outro (boîte à musique, plus lent)
    refrain = [L for L in lignes if L.type_section == "refrain"][:2]
    base = refrain[0].mesure * C.MESURE

    def rejouer(piste, debut, vel, octave=12, etirer=1.0, fin=None):
        for L in refrain:
            for s in L.syllabes:
                d = debut + (s.debut - base) * etirer
                if fin is not None and d >= fin:
                    continue
                piste.note(s.midi + octave, d, min(s.fin - s.debut, 0.4) * etirer, vel)

    rejouer(xylo, 0.0, 82, fin=2 * C.MESURE - C.CROCHE)
    rejouer(marimba, 0.0, 55, octave=0, fin=2 * C.MESURE - C.CROCHE)
    for nom, typ, m0, nb, _sc, tr in B.SECTIONS:
        if typ == "refrain":
            rejouer(xylo, (m0 + 8) * C.MESURE, 80, fin=(m0 + 10) * C.MESURE - C.CROCHE)
            rejouer(glock, (m0 + 8) * C.MESURE, 50, octave=24, fin=(m0 + 10) * C.MESURE - C.CROCHE)
        elif typ == "outro":
            rejouer(boite, m0 * C.MESURE, 62, etirer=1.5, fin=(m0 + 3) * C.MESURE - C.CROCHE)
    return pm


# ===================================================================== bruitages
def _bloup(sr, rnd):
    """Bulle qui éclate : petit glissando sinusoïdal montant."""
    d = rnd.uniform(0.05, 0.09)
    n = int(d * sr)
    tt = np.arange(n) / sr
    f0 = rnd.uniform(380, 650)
    f = f0 * (1 + 2.2 * tt / d)
    y = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt / (d * 0.45))
    a = int(0.004 * sr)
    y[:a] *= np.linspace(0, 1, a)
    return y


def _splash(sr, rnd):
    """Éclaboussure : bruit filtré avec plusieurs petites gouttes."""
    n = int(0.45 * sr)
    tt = np.arange(n) / sr
    bruit = rnd_bruit(n, rnd)
    b, a = signal.butter(2, [900 / (sr / 2), 7000 / (sr / 2)], "band")
    y = signal.lfilter(b, a, bruit) * np.exp(-tt / 0.09)
    for _ in range(4):
        g = _bloup(sr, rnd) * 0.35
        i = int(rnd.uniform(0.04, 0.25) * sr)
        y[i:i + len(g)] += g[: n - i]
    return y


def rnd_bruit(n, rnd):
    return np.random.default_rng(rnd.randint(0, 1 << 30)).standard_normal(n)


def _couic(sr):
    """Couinement du canard en caoutchouc (deux petites notes)."""
    res = []
    for f, d in ((1250, 0.09), (1550, 0.12)):
        n = int(d * sr)
        tt = np.arange(n) / sr
        ff = f * (1 + 0.04 * np.sin(2 * np.pi * 28 * tt))
        ph = 2 * np.pi * np.cumsum(ff) / sr
        y = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph)) * np.sin(np.pi * tt / d) ** 0.5
        res.append(y)
        res.append(np.zeros(int(0.03 * sr)))
    return np.concatenate(res)


def bruitages(lignes, n):
    """Piste stéréo (n échantillons) de bruitages calés sur les paroles."""
    sr = C.SR
    rnd = random.Random(42)
    g = np.zeros(n)
    d_ = np.zeros(n)

    def poser(y, temps, gain, pan=0.0):
        i = int(temps * sr)
        if i >= n:
            return
        j = min(n, i + len(y))
        g[i:j] += gain * (1 - max(0, pan)) * y[: j - i]
        d_[i:j] += gain * (1 + min(0, pan)) * y[: j - i]

    for L in lignes:
        for m in L.mots:
            mot = m.texte.lower().strip(",!. ")
            if mot.startswith("splash"):
                poser(_splash(sr, rnd), m.debut + 0.05, 0.55, rnd.uniform(-0.5, 0.5))
            elif mot.startswith("bulles"):
                for k in range(5):
                    poser(_bloup(sr, rnd), m.debut + 0.1 + 0.13 * k, 0.5, rnd.uniform(-0.7, 0.7))
            elif mot.startswith("canard"):
                poser(_couic(sr), m.fin + 0.05, 0.35)
            elif mot in B.MOTS_COMPTE and L.section == "couplet 3":
                poser(_bloup(sr, rnd), m.debut + 0.02, 0.8, {"un": -0.5, "deux": 0.0, "trois": 0.5}[mot])
    # bulles qui éclatent doucement pendant les passages instrumentaux et les scènes de bain
    for nom, typ, m0, nb, _sc, _tr in B.SECTIONS:
        if typ in ("intro",):
            zone = (0.3, 2 * C.MESURE)
        elif typ == "refrain":
            zone = ((m0 + 8) * C.MESURE, (m0 + 10) * C.MESURE)
        else:
            continue
        tt = zone[0]
        while tt < zone[1]:
            poser(_bloup(sr, rnd), tt, 0.4, rnd.uniform(-0.8, 0.8))
            tt += rnd.uniform(0.18, 0.5)
    # canard qui couine au début de l'intro
    poser(_couic(sr), 1.2, 0.35, 0.3)
    return np.stack([g, d_], axis=1).astype(np.float32)

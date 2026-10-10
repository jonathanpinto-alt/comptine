"""Accompagnement musical : MIDI (pretty_midi) rendu avec FluidSynth.

Instruments General MIDI : xylophone, glockenspiel, boîte à musique, basse
douce, piano/ukulélé, cordes, flûte, cuivres et petite batterie. L'arrangement
change selon la section (pont plus doux, refrain final plus fourni).
"""
import shutil
import subprocess

import numpy as np
import pretty_midi
import soundfile as sf

from . import config as C
from .chanson import NOTES_ACCORDS, SECTIONS, accords_par_mesure

# programmes General MIDI (numérotation à partir de 0)
PIANO, CELESTA, GLOCK, BOITE, MARIMBA, XYLO = 0, 8, 9, 10, 12, 13
GUITARE_NYLON, BASSE_DOIGTS, BASSE_ACOUSTIQUE = 24, 33, 32
CORDES, PIZZ, TROMPETTE, CUIVRES, FLUTE, PIPEAU = 48, 45, 56, 61, 73, 74
# batterie (canal 10)
KICK, SNARE, CLAP, HAT, HAT_OUVERT, CRASH, TAMBOURIN, CLOCHETTE, MARACAS, TRIANGLE = \
    36, 38, 39, 42, 46, 49, 54, 53, 70, 81


def t(m, temps=0.0):
    """Instant (s) d'une mesure + temps."""
    return m * C.MESURE + temps * C.NOIRE


class Piste:
    def __init__(self, pm, prog, nom, batterie=False):
        self.inst = pretty_midi.Instrument(program=prog, is_drum=batterie, name=nom)
        pm.instruments.append(self.inst)

    def note(self, hauteur, debut, duree, vel=80):
        hauteur = int(hauteur)
        if not 0 <= hauteur <= 127:
            return
        vel = int(max(1, min(127, vel)))
        self.inst.notes.append(pretty_midi.Note(vel, hauteur, debut, debut + duree))


def hauteur_accord(acc, tr, octave_base):
    """Notes de l'accord, fondamentale à l'octave donnée (ex. 48 = C3)."""
    notes = NOTES_ACCORDS[acc]
    racine = octave_base + (notes[0] + tr) % 12
    res = [racine]
    for n in notes[1:]:
        h = octave_base + (n + tr) % 12
        while h <= res[-1]:
            h += 12
        res.append(h)
    return res


def composer(lignes):
    pm = pretty_midi.PrettyMIDI(initial_tempo=C.BPM)
    xylo = Piste(pm, XYLO, "Xylophone")
    glock = Piste(pm, GLOCK, "Glockenspiel")
    boite = Piste(pm, BOITE, "Boîte à musique")
    basse = Piste(pm, BASSE_ACOUSTIQUE, "Basse")
    piano = Piste(pm, PIANO, "Piano")
    ukulele = Piste(pm, GUITARE_NYLON, "Guitare")
    cordes = Piste(pm, CORDES, "Cordes")
    flute = Piste(pm, PIPEAU, "Flûte")
    cuivres = Piste(pm, CUIVRES, "Cuivres")
    marimba = Piste(pm, MARIMBA, "Marimba")
    batt = Piste(pm, 0, "Batterie", batterie=True)

    accords = accords_par_mesure()
    N = len(accords)

    # ----------------------------------------------------------- accompagnement
    for m, (acc, tr, typ) in enumerate(accords):
        racine = hauteur_accord(acc, tr, 36)[0]          # basse vers C2–B2
        quinte = racine + 7
        triade = hauteur_accord(acc, tr, 60)
        triade_g = hauteur_accord(acc, tr, 55)
        fin_morceau = m == N - 1

        if typ == "pont":
            # doux : cordes tenues, boîte à musique en arpèges, basse ronde
            cordes.note(triade_g[0], t(m), C.MESURE, 55)
            for n in triade_g[1:]:
                cordes.note(n, t(m), C.MESURE, 45)
            basse.note(racine, t(m), C.MESURE * 0.95, 60)
            arp = [triade[0] + 12, triade[1] + 12, triade[2] + 12, triade[1] + 12]
            for k in range(8):
                boite.note(arp[k % 4], t(m, k * 0.5), 0.6, 58)
            batt.note(TRIANGLE, t(m), 0.5, 35)
            if m == 40:             # dernière mesure du pont : petit roulement qui réveille
                for k in range(8):
                    batt.note(SNARE, t(m, 2 + k * 0.25), 0.1, 30 + 8 * k)
                batt.note(MARACAS, t(m, 3.5), 0.1, 70)
            continue

        energie = {"intro": 1, "couplet": 1, "refrain": 2, "final": 3, "outro": 1}[typ]

        if fin_morceau:
            # accord final tenu + crash
            for n in triade + [triade[0] + 12]:
                glock.note(n + 12, t(m), 2.0, 90)
                xylo.note(n, t(m), 1.0, 90)
                cordes.note(n - 12, t(m), C.MESURE, 70)
            basse.note(racine, t(m), C.MESURE, 90)
            batt.note(CRASH, t(m), 2.0, 90)
            batt.note(KICK, t(m), 0.3, 110)
            continue

        # basse : fondamentale / quinte en noires (croches dans le final)
        if energie >= 3:
            motif = [racine, racine + 12, quinte, racine + 12, racine, racine + 12, quinte, racine + 7]
            for k, h in enumerate(motif):
                basse.note(h, t(m, k * 0.5), C.CROCHE * 0.9, 95 if k % 2 == 0 else 75)
        else:
            for k, h in enumerate([racine, quinte, racine + 12, quinte]):
                basse.note(h, t(m, k), C.NOIRE * 0.85, 92 if k % 2 == 0 else 72)

        # accords : ukulélé « boom-chick » en couplet, piano en refrain
        if typ in ("couplet", "intro", "outro"):
            for k in (0.5, 1.5, 2.5, 3.5):
                for n in triade:
                    ukulele.note(n, t(m, k), C.CROCHE * 0.9, 62)
        else:
            for k in (0, 1, 1.5, 2, 3, 3.5):
                for n in triade:
                    piano.note(n, t(m, k), C.CROCHE * 0.9, 70 if k in (0, 2) else 55)
        if energie >= 3:
            for n in triade:
                cordes.note(n, t(m), C.MESURE, 55)
            # cuivres : petites ponctuations sur le contretemps
            if m % 2 == 1:
                for n in triade:
                    cuivres.note(n, t(m, 1.5), 0.25, 78)
                    cuivres.note(n, t(m, 2.5), 0.4, 82)

        # batterie
        for k in range(4):
            if k in (0, 2):
                batt.note(KICK, t(m, k), 0.2, 100 if energie > 1 else 85)
            else:
                batt.note(CLAP if energie >= 2 else SNARE, t(m, k), 0.2, 85 if energie >= 2 else 60)
            batt.note(MARACAS, t(m, k + 0.5), 0.1, 45)
        if energie >= 2:
            for k in range(8):
                batt.note(TAMBOURIN, t(m, k * 0.5), 0.1, 70 if k % 2 else 45)
        if energie >= 3:
            batt.note(KICK, t(m, 2.5), 0.2, 80)
            for k in range(8):
                batt.note(HAT, t(m, k * 0.5), 0.1, 55)
        if typ == "intro" and m == 0:
            batt.note(CLOCHETTE, t(m), 1.0, 80)

    # crash sur chaque début de section (sauf intro et pont)
    for nom, typ, m0, nb, _d, tr in SECTIONS:
        if m0 > 0 and typ not in ("pont",):
            batt.note(CRASH, t(m0), 1.5, 70 if typ != "final" else 95)

    # ----------------------------------------------------------- mélodie
    # flûte douce qui double toujours la voix (aide la justesse perçue)
    # glockenspiel en plus dans les refrains, xylophone dans le final
    for L in lignes:
        for s in L.syllabes:
            d = (s.fin - s.debut) * 0.95
            flute.note(s.midi, s.debut, d, 52 if L.type_section != "pont" else 40)
            if L.type_section in ("refrain", "final"):
                glock.note(s.midi + 12, s.debut, min(d, 0.6), 62)
            if L.type_section == "final":
                xylo.note(s.midi, s.debut, min(d, 0.3), 70)
            if L.type_section == "pont":
                cordes.note(s.midi, s.debut, d, 35)

    # petites réponses de xylophone/marimba dans les respirations des couplets
    for L in lignes:
        if L.type_section == "couplet":
            fin_ligne = (L.mesure + 2) * C.MESURE
            acc, tr, _ = accords[min(L.mesure + 1, N - 1)]
            tri = hauteur_accord(acc, tr, 72)
            for k, n in enumerate([tri[0], tri[1], tri[2], tri[0] + 12]):
                xylo.note(n, fin_ligne - C.NOIRE + k * C.DOUBLE, C.DOUBLE, 72)

    # intro : le xylophone annonce la mélodie du refrain (2 premières lignes)
    refrains = [L for L in lignes if L.type_section == "refrain"][:2]
    decal = refrains[0].mesure * C.MESURE if refrains else 0
    for L in refrains:
        for s in L.syllabes:
            debut = s.debut - decal
            if debut < 3 * C.MESURE:
                xylo.note(s.midi + 12, debut, min(s.fin - s.debut, 0.4), 85)
                marimba.note(s.midi, debut, min(s.fin - s.debut, 0.4), 60)
    # outro : glockenspiel rejoue la fin du refrain (lignes 3-4), en descendant d'octave
    refrains = [L for L in lignes if L.type_section == "refrain"][2:4]
    if refrains:
        decal = refrains[0].mesure * C.MESURE - 65 * C.MESURE
        for L in refrains:
            for s in L.syllabes:
                debut = s.debut - decal
                if debut < 66 * C.MESURE:
                    glock.note(s.midi + 12, debut, min(s.fin - s.debut, 0.5), 60)
                    xylo.note(s.midi, debut, min(s.fin - s.debut, 0.3), 65)
    return pm


def soundfont():
    for p in C.SOUNDFONT_CANDIDATS:
        if p.exists():
            return p
    raise SystemExit("Aucune soundfont General MIDI trouvée (apt install fluid-soundfont-gm)")


def rendre(pm, dossier):
    """Écrit musique.mid puis musique.wav (stéréo 44,1 kHz) via FluidSynth."""
    if not shutil.which("fluidsynth"):
        raise SystemExit("fluidsynth manquant (apt install fluidsynth)")
    mid = dossier / "musique.mid"
    wav = dossier / "musique.wav"
    pm.write(str(mid))
    subprocess.run(["fluidsynth", "-ni", "-g", "0.8", "-r", str(C.SR), "-F", str(wav),
                    str(soundfont()), str(mid)], check=True, capture_output=True)
    x, sr = sf.read(wav, dtype="float32")
    assert sr == C.SR, sr
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    n = int(round(C.DUREE_TOTALE * C.SR))
    x = np.pad(x, ((0, max(0, n - len(x))), (0, 0)))[:n]
    # fondu de sortie sur la dernière demi-seconde
    f = int(0.5 * C.SR)
    x[-f:] *= np.linspace(1, 0, f)[:, None]
    return x

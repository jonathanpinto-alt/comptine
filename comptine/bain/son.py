"""Bande son fournie (chanson déjà produite) : ordre des lignes chantées, calage et montage.

La chanson fournie (assets/bain/son/chanson.mp3, 2 min 57,7 s, 144 BPM) chante les
mêmes paroles, mais dans son propre ordre. L'intro, le couplet 1, le refrain et le
couplet 2 y sont repris une deuxième fois, ainsi que le couplet 3.
BLOCS donne, pour chaque passage chanté (repéré dans la voix isolée), les lignes
qu'il contient. `outils/aligner_son.py` place ensuite chaque syllabe sur les attaques
de la voix et écrit assets/bain/son/alignement.json, utilisé pour le karaoké et le montage.
"""
import json

from .. import config as C
from ..chanson import Ligne
from ..voix import LIAISONS, VOYELLES, Mot, decouper_mots, nettoyer, phonemiser, syllaber
from . import chanson as B

DOSSIER = C.ASSETS / "bain" / "son"
AUDIO = DOSSIER / "chanson.mp3"
ALIGNEMENT = DOSSIER / "alignement.json"
BPM = 144.0                           # tempo mesuré (grille de battements très stable)
PHASE = 0.207                         # instant du 1er battement modulo la période (s)

# lignes des paroles (définitives) : clé -> (texte, section, type)
PAROLES = {}
for _i, (_txt, *_r) in enumerate(B.INTRO):
    PAROLES[f"I{_i + 1}"] = (_txt, "intro", "intro")
for _n, _c in (("C1", "couplet 1"), ("C2", "couplet 2"), ("C3", "couplet 3")):
    for _i, (_txt, *_r) in enumerate(B.COUPLETS[_c]):
        PAROLES[f"{_n}_{_i + 1}"] = (_txt, _c, "couplet")
for _i, (_txt, *_r) in enumerate(B.REFRAIN):
    PAROLES[f"R{_i + 1}"] = (_txt, "refrain", "refrain")
for _i, (_txt, *_r) in enumerate(B.FIN):
    PAROLES[f"F{_i + 1}"] = (_txt, "fin", "fin")

# (début s, fin s, lignes chantées dans ce passage) — repérés sur la voix isolée
BLOCS = [
    (2.40, 6.60, ["I1"]), (7.50, 11.40, ["I2"]),
    (14.40, 17.10, ["C1_1"]), (17.70, 20.40, ["C1_2"]), (20.90, 24.05, ["C1_3"]), (24.40, 27.35, ["C1_4"]),
    (27.38, 30.50, ["R1"]), (30.70, 33.80, ["R2"]), (34.00, 37.25, ["R3"]), (37.55, 40.90, ["R4"]),
    (41.10, 43.70, ["C2_1"]), (44.35, 47.55, ["C2_2"]), (47.65, 50.45, ["C2_3"]), (50.90, 53.80, ["C2_4"]),
    (54.05, 57.10, ["R1"]), (57.40, 60.45, ["R2"]), (60.80, 63.85, ["R3"]), (64.25, 70.50, ["R4", "C3_1"]),
    (70.70, 73.70, ["C3_2"]), (74.05, 77.25, ["C3_3"]), (77.25, 81.40, ["C3_4"]),
    (84.40, 86.95, ["I1"]), (87.70, 90.25, ["I2"]),
    (91.05, 93.80, ["C1_1"]), (94.35, 100.55, ["C1_2", "R1"]), (100.70, 103.80, ["R2"]), (104.05, 107.10, ["R3"]),
    (107.55, 113.75, ["R4", "C2_1"]), (113.90, 117.55, ["C2_2"]), (117.55, 120.50, ["C2_3"]),
    (120.65, 124.80, ["C2_4"]),
    (127.35, 130.40, ["C3_1"]), (130.70, 133.70, ["C3_2"]), (134.05, 137.25, ["C3_3"]), (137.55, 141.40, ["C3_4"]),
    (144.00, 147.10, ["R1"]), (147.40, 150.50, ["R2"]), (150.80, 153.80, ["R3"]),
    (154.25, 160.30, ["R4", "F1"]), (160.45, 163.85, ["F2"]), (164.00, 167.05, ["F3"]), (167.35, 171.60, ["F4"]),
]

# Montage : (index de la ligne chantée où commence le plan, scène).
# L'ordre demandé (1, 2, 3, 4, 5, 3, 4, 3, 4, 5, 6, 6, 3, 4, 5, 7) est suivi section par section ;
# la reprise du milieu (intro, couplet 1, refrain, couplet 2 et couplet 3 rechantés, 84-142 s)
# reprend les scènes qui illustrent ces mêmes paroles.
MONTAGE = [
    (0, 1), (1, 2),                 # intro
    (2, 3), (4, 4),                 # couplet 1
    (6, 5), (8, 3),                 # refrain
    (10, 4), (12, 3),               # couplet 2
    (14, 4), (16, 5),               # refrain
    (18, 6), (20, 6),               # couplet 3
    (22, 1), (23, 2),               # reprise : intro
    (24, 3), (26, 5), (28, 3),      # couplet 1 + refrain
    (30, 4), (32, 3),               # couplet 2
    (34, 6), (36, 6),               # couplet 3
    (38, 3), (40, 4),               # refrain
    (42, 5), (44, 7),               # fin
]


def texte(cle):
    return PAROLES[cle][0]


def lignes_chantees():
    """Liste ordonnée des clés de lignes chantées."""
    return [k for _a, _b, cles in BLOCS for k in cles]


def syllabes_ligne(texte):
    """Mots affichés et syllabes (espeak) d'une ligne, comme voix.preparer_lignes."""
    mots_txt = decouper_mots(texte)
    cles = [nettoyer(m) for m in mots_txt]
    mots, syls = [], []
    for i, (m, cle) in enumerate(zip(mots_txt, cles)):
        ph = list(phonemiser(cle))
        if i > 0 and cles[i - 1] in LIAISONS and ph and ph[0][0] in VOYELLES \
                and not mots_txt[i - 1].rstrip().endswith((",", "!", "?", ".", "…")):
            ph.insert(0, (LIAISONS[cles[i - 1]], 60))
        s = syllaber(ph, i)
        mots.append(Mot(m, syllabes=s))
        syls.extend(s)
    return mots, syls


def construire_lignes():
    """Lignes (objets Ligne avec mots et syllabes) calées sur la chanson fournie."""
    donnees = json.loads(ALIGNEMENT.read_text(encoding="utf-8"))
    lignes = []
    for el in donnees["lignes"]:
        texte, section, typ = PAROLES[el["cle"]]
        L = Ligne(texte, section, typ, 0, [], 0)
        mots, syls = syllabes_ligne(texte)
        assert len(syls) == len(el["syllabes"]), el["cle"]
        for s, (d, f) in zip(syls, el["syllabes"]):
            s.debut, s.fin = d, f
        for m in mots:
            m.debut = m.syllabes[0].debut
            m.fin = m.syllabes[-1].fin
        L.syllabes, L.mots = syls, mots
        lignes.append(L)
    return lignes


def plan_de_montage(lignes, duree):
    """Plans (début_s, fin_s, scène, index, occurrence) d'après les lignes chantées."""
    debuts = [max(0.0, lignes[i].mots[0].debut - 0.35) if i else 0.0 for i, _sc in MONTAGE]
    plans, vus = [], {}
    for k, ((_i, sc), d) in enumerate(zip(MONTAGE, debuts)):
        f = debuts[k + 1] if k + 1 < len(debuts) else duree
        vus[sc] = vus.get(sc, 0) + 1
        plans.append((d, f, sc, k, vus[sc] - 1))
    return plans

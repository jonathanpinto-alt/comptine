"""Bande son fournie de « Toc toc toc » : lignes chantées, calage et plans.

La chanson (assets/toc/son/chanson.mp3, « Toc toc toc 2 », 2 min 17,6 s, ≈ 146 BPM)
chante une ligne par mesure d'environ 3,3 s, exactement dans l'ordre des paroles :
intro, couplet 1, refrain, couplet 2, refrain, pont, couplet 3, refrain final ×2
(avec « Encore une fois ! »), outro. BLOCS donne les passages chantés (repérés sur la voix isolée, Whisper +
grille de mesures) et les lignes qu'ils contiennent ; `python outils/aligner_son.py
--chanson toc` place ensuite chaque syllabe et écrit assets/toc/son/alignement.json.
"""
import json

from .. import config as C
from ..chanson import Ligne
from ..bain.son import syllabes_ligne  # noqa: F401  (réutilisé par l'aligneur)
from . import chanson as T

DOSSIER = C.ASSETS / "toc" / "son"
AUDIO = DOSSIER / "chanson.mp3"
ALIGNEMENT = DOSSIER / "alignement.json"
BPM = 146.5
PHASE = 0.16

F, H, CH = T.F, T.H, T.CH

# clé -> (section, type, segments [(texte, voix, personnage)])
PAROLES = {"I": ("intro", "intro", T.PAROLES["intro"][0][2]),
           "E": ("refrain final", "final", [("Encore une fois !", CH, "tous")]),
           "O": ("outro", "outro", T.PAROLES["outro"][0][2])}
for _nom, _cle in (("couplet 1", "C1"), ("couplet 2", "C2"), ("pont", "P"), ("couplet 3", "C3")):
    _typ = "pont" if _cle == "P" else "couplet"
    for _i, (_m, _s, _segs) in enumerate(T.PAROLES[_nom]):
        PAROLES[f"{_cle}_{_i + 1}"] = (_nom, _typ, _segs)
for _i, _segs in enumerate(T.REFRAIN):
    PAROLES[f"R{_i + 1}"] = ("refrain", "refrain", _segs)
    PAROLES[f"RF{_i + 1}"] = ("refrain final", "final", _segs)


def texte(cle):
    return " ".join(s[0] for s in PAROLES[cle][2])


# (début s, fin s, lignes chantées dans ce passage)
BLOCS = [
    (3.30, 6.10, ["I"]),
    (12.75, 19.45, ["C1_1", "C1_2"]), (19.45, 22.40, ["C1_3"]), (22.95, 25.65, ["C1_4"]),
    (26.20, 28.95, ["R1"]), (29.50, 32.35, ["R2"]), (32.80, 35.45, ["R3"]), (35.45, 38.40, ["R4"]),
    (38.85, 41.30, ["C2_1"]), (42.10, 44.70, ["C2_2"]), (45.40, 48.00, ["C2_3"]), (49.00, 51.70, ["C2_4"]),
    (52.30, 55.10, ["R1"]), (55.60, 58.45, ["R2"]), (58.85, 61.35, ["R3"]), (61.35, 64.35, ["R4"]),
    (65.20, 67.90, ["P_1"]), (68.20, 70.70, ["P_2"]), (70.85, 76.65, ["P_3", "P_4"]),
    (78.30, 83.80, ["C3_1", "C3_2"]), (84.75, 90.95, ["C3_3", "C3_4"]), (91.10, 96.40, ["C3_5", "C3_6"]),
    (97.75, 100.50, ["RF1"]), (101.00, 103.75, ["RF2"]), (104.25, 106.70, ["RF3"]), (106.70, 109.40, ["RF4"]), (109.40, 111.10, ["E"]),
    (111.10, 113.50, ["RF1"]), (114.00, 116.75, ["RF2"]), (117.20, 120.00, ["RF3"]), (120.00, 125.00, ["RF4"]),
    (126.90, 130.70, ["O"]),
]

# décor de chaque section ; le plan commence avec la 1re ligne chantée de la section
DECORS = {"intro": "colline", "couplet 1": "cuisine", "refrain": "salon", "couplet 2": "porte", "pont": "fenetre",
          "couplet 3": "porte_nuit", "refrain final": "fete", "outro": "colline_nuit"}


def construire_lignes():
    donnees = json.loads(ALIGNEMENT.read_text(encoding="utf-8"))
    lignes = []
    for el in donnees["lignes"]:
        section, typ, segs = PAROLES[el["cle"]]
        L = Ligne(texte(el["cle"]), section, typ, 0, [], 0)
        L.segments = segs
        L.cle = el["cle"]
        mots, syls = syllabes_ligne(L.texte)
        assert len(syls) == len(el["syllabes"]), el["cle"]
        for s, (d, f) in zip(syls, el["syllabes"]):
            s.debut, s.fin = d, f
        for m in mots:
            m.debut, m.fin = m.syllabes[0].debut, m.syllabes[-1].fin
        L.syllabes, L.mots = syls, mots
        lignes.append(L)
    return lignes


def plans(lignes, duree):
    """[(début_s, fin_s, décor, section, index du refrain final)] : un plan par section chantée."""
    res = []
    prec = None
    nb_final = 0
    for i, L in enumerate(lignes):
        nouveau = prec is None or L.section != prec.section
        # refrain final : un nouveau plan à chaque reprise (RF1 après autre chose que « E »)
        if L.type_section == "final" and getattr(L, "cle", "") == "RF1":
            nouveau = True
        if nouveau:
            debut = 0.0 if not res else max(res[-1][0] + 1.0, L.mots[0].debut - 0.45)
            if L.type_section == "final" and getattr(L, "cle", "") == "RF1":
                nb_final += 1
            res.append([debut, None, DECORS[L.section], L.section, nb_final])
        prec = L
    for k in range(len(res)):
        res[k][1] = res[k + 1][0] if k + 1 < len(res) else duree
    return [tuple(p) for p in res]

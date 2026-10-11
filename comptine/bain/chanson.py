"""Paroles, structure, accords et mélodie de « C'est l'heure du bain ».

96 BPM, 4/4, 72 mesures = 3 min pile. Chaque ligne chantée occupe 2 mesures.
Les paroles sont définitives : elles sont reproduites telles quelles.
La mélodie est écrite note par note : pour chaque ligne, une hauteur MIDI et
une durée (en doubles croches) par syllabe chantée. Les syllabes sont celles
que donne espeak-ng (« lave » = 1 syllabe, « regarde-moi » = 3…).

Chaque section est montée sur deux scènes (ordre de montage demandé :
1, 2, 3, 4, 5, 3, 4, 3, 4, 5, 6, 6, 3, 4, 5, 7).
"""
from ..chanson import Ligne

TITRE = "C'est l'heure du bain !"
BPM = 96
NB_MESURES = 72                      # 72 x 2,5 s = 180 s
DUREE_MIN, DUREE_MAX = 178.0, 182.0

# --------------------------------------------------------------------------
# Structure : (nom, type, mesure de début, nb de mesures, (scène A, scène B), transposition)
# La scène B commence à la mesure `m0 + COUPE[type]` (au début de la 3e ligne).
# --------------------------------------------------------------------------
SECTIONS = [
    ("intro",     "intro",   0, 6, (1, 2), 0),
    ("couplet 1", "couplet", 6, 8, (3, 4), 0),
    ("refrain",   "refrain", 14, 10, (5, 3), 0),
    ("couplet 2", "couplet", 24, 8, (4, 3), 0),
    ("refrain",   "refrain", 32, 10, (4, 5), 0),
    ("couplet 3", "couplet", 42, 8, (6, 6), 0),
    ("refrain",   "refrain", 50, 10, (3, 4), 0),
    ("fin",       "fin",     60, 8, (5, 7), 0),
    ("outro",     "outro",   68, 4, (7, 7), 0),
]
COUPE = {"intro": 4, "couplet": 4, "refrain": 4, "fin": 4, "outro": 4}

ACCORDS_SECTION = {
    "intro":   ["C", "G", "C", "Am", "F", "G"],
    "couplet": ["C", "C", "Dm", "G", "C", "C", "F", "C"],
    # 8 mesures chantées + 2 mesures instrumentales (« splash » au xylophone)
    "refrain": ["C", "C", "F", "G", "F", "G", "C", "C", "F", "G"],
    "fin":     ["C", "F", "G", "C", "C", "F", "G", "C"],
    "outro":   ["F", "G", "C", "C"],
}

# --------------------------------------------------------------------------
# Paroles (définitives) avec leur mélodie : (texte, notes MIDI, durées en doubles croches)
# --------------------------------------------------------------------------
INTRO = [
    ("C’est l’heure du bain, tralala",
     [67, 64, 67, 72, 69, 67, 64], [2, 2, 2, 6, 2, 2, 8]),
    ("Viens avec moi, on va jouer ça",
     [65, 65, 67, 69, 67, 65, 64, 62], [2, 2, 2, 6, 2, 2, 4, 8]),
]
COUPLETS = {
    "couplet 1": [
        ("C’est l’heure du bain, l’heure du bain",
         [60, 64, 67, 67, 69, 67, 64], [2, 2, 2, 6, 2, 2, 8]),
        ("Viens te laver, prends ta main",
         [65, 65, 64, 62, 64, 65, 67], [2, 2, 2, 6, 2, 2, 8]),
        ("De l’eau qui coule, des bulles qui dansent",
         [60, 64, 67, 67, 69, 69, 67, 64], [2, 2, 2, 6, 2, 2, 2, 6]),
        ("On va jouer, quelle chance !",
         [65, 65, 67, 69, 72], [2, 2, 8, 4, 12]),
    ],
    "couplet 2": [
        ("Le canard jaune nage avec toi",
         [60, 64, 67, 67, 69, 67, 64, 64], [2, 2, 4, 4, 2, 2, 2, 6]),
        ("Le shampoing mousse sur tes cheveux, regarde-moi",
         [65, 65, 65, 64, 62, 62, 64, 65, 64, 65, 67], [1, 1, 2, 2, 2, 2, 2, 4, 2, 2, 8]),
        ("On rince tout, on frotte bien fort",
         [60, 64, 67, 69, 67, 67, 64], [2, 2, 8, 2, 2, 2, 6]),
        ("Après le bain, on est en or",
         [65, 65, 67, 69, 69, 69, 71, 72], [2, 2, 2, 4, 2, 2, 2, 12]),
    ],
    "couplet 3": [
        ("On compte les bulles, un, deux, trois",
         [60, 64, 67, 67, 64, 67, 72], [2, 2, 2, 6, 4, 4, 8]),
        ("On chante encore, toi et moi",
         [65, 65, 64, 62, 64, 65, 67], [2, 2, 2, 6, 2, 2, 8]),
        ("L’eau est tiède, tout est calme",
         [60, 64, 67, 69, 67, 64], [2, 2, 8, 2, 2, 8]),
        ("On se détend, quel programme",
         [65, 65, 67, 69, 69, 71, 72], [2, 2, 2, 6, 2, 2, 12]),
    ],
}
REFRAIN = [
    ("Splash splash splash, dans la baignoire",
     [67, 67, 67, 72, 71, 69, 67], [2, 2, 4, 2, 2, 4, 12]),
    ("Splash splash splash, quelle victoire",
     [65, 65, 65, 69, 71, 74], [2, 2, 4, 2, 2, 12]),
    ("Lave tes mains, lave tes pieds",
     [72, 71, 69, 71, 69, 67], [2, 2, 8, 2, 2, 8]),
    ("Tout propre, tout beau, ohé !",
     [64, 64, 67, 67, 67, 72], [2, 4, 2, 4, 4, 8]),
]
FIN = [
    ("Maintenant tout propre, dans ta serviette",
     [64, 64, 67, 67, 69, 67, 65, 65], [2, 2, 2, 6, 2, 2, 4, 8]),
    ("Un gros câlin, une bonne fête",
     [62, 62, 65, 67, 65, 64, 60], [2, 2, 2, 6, 2, 2, 8]),
    ("Dodo t’attend, ferme les yeux",
     [67, 64, 67, 64, 62, 64, 65], [2, 2, 2, 6, 2, 2, 8]),
    ("C’est l’heure du bain, le meilleur des jeux",
     [67, 65, 64, 62, 62, 64, 62, 59, 60], [2, 2, 2, 6, 2, 2, 2, 2, 8]),
]

# mots déclencheurs d'animations (éclaboussures, comptage…)
MOTS_SPLASH = ("splash",)
MOTS_COMPTE = ("un", "deux", "trois")


def _ligne(spec, nom, typ, mesure, transpo=0):
    texte, notes, durees = spec
    return Ligne(texte, nom, typ, mesure, notes, sum(durees), transpo=transpo, notes=notes, durees=durees)


def construire_lignes():
    """Renvoie la liste ordonnée des lignes chantées avec leur placement."""
    lignes = []
    for nom, typ, m0, nb, _scenes, tr in SECTIONS:
        if typ == "intro":
            for i, spec in enumerate(INTRO):
                lignes.append(_ligne(spec, nom, typ, m0 + 2 + 2 * i))
        elif typ == "couplet":
            for i, spec in enumerate(COUPLETS[nom]):
                lignes.append(_ligne(spec, nom, typ, m0 + 2 * i))
        elif typ == "refrain":
            for i, spec in enumerate(REFRAIN):
                lignes.append(_ligne(spec, nom, typ, m0 + 2 * i, tr))
        elif typ == "fin":
            for i, spec in enumerate(FIN):
                lignes.append(_ligne(spec, nom, typ, m0 + 2 * i))
    return lignes


def accords_par_mesure():
    """Liste (longueur NB_MESURES) de (accord, transposition, type_section)."""
    res = []
    for nom, typ, m0, nb, _scenes, tr in SECTIONS:
        acc = ACCORDS_SECTION[typ]
        for k in range(nb):
            res.append((acc[k % len(acc)], tr, typ))
    assert len(res) == NB_MESURES
    return res


def plan_de_montage(mesure_s):
    """Liste des plans : (début_s, fin_s, numéro de scène, index de section, occurrence de la scène)."""
    plans = []
    vus = {}
    for k, (nom, typ, m0, nb, scenes, _tr) in enumerate(SECTIONS):
        coupe = m0 + COUPE[typ]
        for j, (a, b) in enumerate(((m0, coupe), (coupe, m0 + nb))):
            sc = scenes[j]
            if plans and plans[-1][2] == sc and plans[-1][3] == k - 1 and nom == "outro":
                # l'outro prolonge le dernier plan (scène 7) sans coupure
                d, _f, s_, i_, o_ = plans[-1]
                plans[-1] = (d, b * mesure_s, s_, i_, o_)
                continue
            vus[sc] = vus.get(sc, 0) + 1
            plans.append((a * mesure_s, b * mesure_s, sc, k, vus[sc] - 1))
    return plans

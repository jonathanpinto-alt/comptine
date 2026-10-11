"""Paroles, structure et minutage provisoire de « Toc toc toc, qui est là ? ».

La bande son est fournie à part. En attendant, les lignes sont posées sur une
grille de 110 BPM (69 mesures ≈ 2 min 30), comme la structure demandée :
intro (4) → couplet 1 → refrain → couplet 2 → refrain → pont calme → couplet 3
→ refrain final ×2 → outro. Quand le son arrive, les paroles sont recalées sur
la voix (voir son.py).

Chaque ligne est une suite de segments (texte, voix, personnage) : la voix est
« femme » (soliste), « homme » (réponses) ou « choeur » ; le personnage indique
qui ouvre la bouche à l'écran.
"""
from ..chanson import Ligne

TITRE = "Toc toc toc, qui est là ?"
BPM = 110
NB_MESURES = 69
DUREE_MIN, DUREE_MAX = 145.0, 155.0

# (nom, type, mesure de début, nb de mesures, décor)
SECTIONS = [
    ("intro", "intro", 0, 4, "colline"),
    ("couplet 1", "couplet", 4, 8, "cuisine"),
    ("refrain", "refrain", 12, 8, "salon"),
    ("couplet 2", "couplet", 20, 8, "porte"),
    ("refrain", "refrain", 28, 8, "salon"),
    ("pont", "pont", 36, 5, "fenetre"),
    ("couplet 3", "couplet", 41, 8, "porte_nuit"),
    ("refrain final", "final", 49, 8, "fete"),
    ("refrain final", "final", 57, 8, "fete"),
    ("outro", "outro", 65, 4, "colline_nuit"),
]

F, H, CH = "femme", "homme", "choeur"

# (mesure, nb de doubles croches, segments [(texte, voix, personnage)])
REFRAIN = [
    [("Toc toc toc, qui est là ?", CH, "tous")],
    [("Ouvre vite, n'aie pas peur, ça va !", CH, "tous")],
    [("Toc toc toc, entre donc,", CH, "tous")],
    [("Il fait chaud dans ma maison !", CH, "tous")],
]
PAROLES = {
    "intro": [(2, 24, [("Toc toc toc ! Qui est là ?", CH, "tous")])],
    "couplet 1": [
        (4, 28, [("Il pleut, il pleut sur la colline,", F, "lapin")]),
        (6, 28, [("Petit Lapin est dans sa cuisine.", F, "lapin")]),
        (8, 28, [("Mais tout à coup, qu'est-ce que c'est ?", F, "lapin")]),
        (10, 28, [("Quelqu'un frappe à son volet !", F, "lapin")]),
    ],
    "couplet 2": [
        (20, 28, [("Qui est là ?", F, "lapin"), ("C'est moi, Cochon !", H, "cochon")]),
        (22, 28, [("J'ai la queue en tire-bouchon !", H, "cochon")]),
        (24, 28, [("Et puis là ?", F, "lapin"), ("C'est moi, Biquette !", H, "biquette")]),
        (26, 28, [("Plic, ploc, plic, sur mes lunettes !", H, "biquette")]),
    ],
    "pont": [
        (36, 16, [("Chut, chut, la pluie fait plic, ploc,", F, "lapin")]),
        (37, 16, [("Les amis sont au chaud, ploc, ploc.", F, "lapin")]),
        (38, 16, [("Hou hou ! Qui toque au carreau ?", F, "hibou")]),
        (39, 16, [("C'est Hibou, tout mouillé, oh oh !", F, "hibou")]),
    ],
    "couplet 3": [
        (41, 16, [("Toc… toc… toc… tout doucement,", F, "lapin")]),
        (42, 16, [("Encore quelqu'un ? On attend…", F, "lapin")]),
        (43, 16, [("Deux gros yeux et des dents pointues…", F, "lapin")]),
        (44, 16, [("Oh là là, qui est venu ?", F, "lapin")]),
        (45, 28, [("C'est Croco, gentil comme tout,", H, "croco")]),
        (47, 28, [("Avec un gâteau pour vous !", H, "croco")]),
    ],
    "outro": [(66, 24, [("Toc toc toc… Bonne nuit, les amis !", CH, "tous")])],
}

# petite mélodie guide (do majeur, une note par croche) pour la piste témoin
GABARITS = {
    "intro": [67, 67, 67, 72, 69, 67, 64, 64, 62, 60, 60, 60],
    "couplet": [[60, 60, 64, 64, 67, 67, 67, 65, 64, 64, 64, 62, 60, 60],
                [65, 65, 65, 64, 62, 62, 65, 64, 62, 62, 62, 64, 67, 67],
                [67, 67, 67, 65, 64, 64, 67, 67, 69, 69, 67, 65, 64, 64],
                [65, 65, 69, 69, 67, 67, 65, 64, 64, 64, 62, 62, 60, 60]],
    "refrain": [[67, 67, 67, 72, 72, 69, 67, 67, 69, 69, 69, 65, 69, 69],
                [67, 67, 64, 64, 67, 67, 64, 64, 62, 62, 62, 64, 62, 62],
                [67, 67, 67, 72, 72, 72, 67, 67, 69, 69, 69, 65, 69, 69],
                [67, 67, 67, 65, 62, 62, 62, 59, 60, 60, 64, 64, 60, 60]],
    "pont": [[64, 64, 64, 62, 60, 60, 59, 57], [65, 65, 64, 62, 60, 60, 60, 60],
             [64, 64, 64, 65, 67, 67, 65, 64], [62, 62, 62, 64, 62, 62, 59, 59]],
}


def segments_lignes():
    """[(section, type, mesure, slots, segments, transpo)] dans l'ordre de la chanson."""
    res = []
    for nom, typ, m0, nb, _d in SECTIONS:
        if typ in ("refrain", "final"):
            tr = 2 if (typ == "final" and m0 == 57) else 0
            for i, segs in enumerate(REFRAIN):
                slots = 24 if (typ == "final" and m0 == 49 and i == 3) else 28
                res.append((nom, typ, m0 + 2 * i, slots, segs, tr))
            if typ == "final" and m0 == 49:
                res.append((nom, typ, m0 + 7, 8, [("Encore une fois !", CH, "tous")], 0))
        else:
            for m, slots, segs in PAROLES[nom]:
                res.append((nom, typ, m, slots, segs, 0))
    return res


def construire_lignes():
    """Lignes (objets Ligne) pour voix.preparer_lignes (minutage provisoire sur la grille)."""
    lignes = []
    for nom, typ, m, slots, segs, tr in segments_lignes():
        texte = " ".join(s_[0] for s_ in segs)
        if typ in ("refrain", "final", "couplet") and slots > 8:
            pos = sum(1 for L in lignes if L.section == nom and L.mesure >= _debut(nom, m))
            gab = GABARITS["couplet" if typ == "couplet" else "refrain"][pos % 4]
        elif typ == "pont":
            gab = GABARITS["pont"][(m - 36) % 4]
        else:
            gab = GABARITS["intro"]
        L = Ligne(texte, nom, typ, m, gab, slots, transpo=tr, style="cri" if slots <= 8 else "chant")
        L.segments = segs
        if texte == "Encore une fois !":
            L.decalage = 8                      # après « maison ! », sur la fin de la mesure
        lignes.append(L)
    return lignes


def _debut(nom, m):
    """Mesure de début de la section `nom` qui contient la mesure m."""
    d = 0
    for n, _t, m0, nb, _d in SECTIONS:
        if n == nom and m0 <= m < m0 + nb:
            d = m0
    return d


def voix_des_mots(L):
    """Pour chaque mot affiché de la ligne : (voix, personnage), d'après les segments."""
    from ..voix import decouper_mots
    res = []
    for texte, voix, perso in L.segments:
        res += [(voix, perso)] * len(decouper_mots(texte))
    return res


def section_a(t, mesure_s):
    m = t / mesure_s
    cur = 0
    for k, s in enumerate(SECTIONS):
        if m >= s[2] - 1e-9:
            cur = k
    return cur

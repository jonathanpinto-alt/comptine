"""Paroles, structure, accords et mélodie de « Bonjour la ferme ! ».

Toute la chanson est décrite sur une grille de mesures (110 BPM, 4/4).
Chaque ligne chantée occupe 2 mesures ; la mélodie est définie par des
« gabarits » (une hauteur MIDI par croche) dans lesquels on vient piocher
la note de chaque syllabe selon sa position rythmique.
"""
from dataclasses import dataclass, field

TITRE = "Bonjour la ferme !"

# --------------------------------------------------------------------------
# Structure : (nom, type, mesure de début, nb de mesures, décor, transposition)
# --------------------------------------------------------------------------
SECTIONS = [
    ("intro",     "intro",   0, 4, "aube",     0),
    ("couplet 1", "couplet", 4, 8, "pre",      0),
    ("refrain",   "refrain", 12, 8, "grange",  0),
    ("couplet 2", "couplet", 20, 8, "mare",    0),
    ("refrain",   "refrain", 28, 8, "grange",  0),
    ("pont",      "pont",    36, 5, "nuit",    0),
    ("couplet 3", "couplet", 41, 8, "foret",   0),
    ("refrain final", "final", 49, 8, "fete",  0),
    ("refrain final", "final", 57, 8, "fete",  2),   # modulation +1 ton
    ("outro",     "outro",   65, 4, "couchant", 0),
]

# --------------------------------------------------------------------------
# Accords (un par mesure) pour chaque type de section
# --------------------------------------------------------------------------
ACCORDS_SECTION = {
    "intro":   ["C", "F", "G", "C"],
    "couplet": ["C", "Am", "F", "G", "C", "Am", "F", "C"],
    "refrain": ["C", "F", "C", "G", "C", "F", "G", "C"],
    "final":   ["C", "F", "C", "G", "C", "F", "G", "C"],
    "pont":    ["Am", "F", "C", "G", "G"],
    "outro":   ["C", "F", "G", "C"],
}

NOTES_ACCORDS = {          # notes (classes de hauteur, C=0) – fondamentale en premier
    "C": [0, 4, 7], "F": [5, 9, 0], "G": [7, 11, 2], "Am": [9, 0, 4],
    "Dm": [2, 5, 9], "Em": [4, 7, 11],
}

# --------------------------------------------------------------------------
# Gabarits mélodiques : 14 croches (la ligne chantée), puis 2 croches de souffle
# --------------------------------------------------------------------------
G = {
    # couplets
    "c1": [60, 60, 64, 64, 67, 67, 67, 65, 64, 64, 64, 62, 60, 60],
    "c2": [65, 65, 65, 64, 62, 62, 65, 64, 62, 62, 62, 64, 67, 67],
    "c3": [67, 67, 67, 65, 64, 64, 67, 67, 69, 69, 67, 65, 64, 64],
    "c4": [65, 65, 69, 69, 67, 67, 65, 64, 64, 64, 62, 62, 60, 60],
    # refrain
    "r1": [67, 67, 67, 64, 72, 72, 67, 67, 69, 69, 69, 65, 69, 69],
    "r2": [67, 67, 64, 64, 67, 67, 64, 64, 62, 62, 62, 64, 62, 62],
    "r3": [64, 64, 64, 67, 72, 72, 72, 67, 69, 69, 69, 65, 69, 69],
    "r4": [67, 67, 67, 65, 62, 62, 62, 59, 60, 60, 64, 64, 60, 60],
    # pont (plus grave, plus doux)
    # (une ligne par mesure : 8 croches)
    "p1": [64, 64, 64, 62, 60, 60, 59, 57],
    "p2": [65, 65, 64, 62, 60, 60, 60, 60],
    "p3": [64, 64, 64, 65, 67, 67, 65, 64],
    "p4": [62, 62, 62, 64, 62, 62, 59, 59],
    # petites interjections
    "cocorico": [67, 67, 69, 72],
    "encore":   [67, 69, 71, 74],
    "aurevoir": [67, 67, 65, 65, 64, 64, 62, 62, 64, 60, 60, 60],
}

COUPLETS = {
    "couplet 1": [
        "Le soleil se lève, cocorico !",
        "Le coq chante tout là-haut.",
        "La vache dit « meuh » dans le pré,",
        "Elle a du bon lait à donner !",
    ],
    "couplet 2": [
        "Le petit canard fait coin-coin,",
        "Il nage, il nage dans le bassin.",
        "Le cochon rose fait groin-groin,",
        "Il se roule dans la boue, c'est bien !",
    ],
    "couplet 3": [
        "Cocorico, le jour est là !",
        "Le cheval galope, hop là, hop là !",
        "Les poussins font piou-piou-piou,",
        "Tout le monde se lève, debout, debout !",
    ],
}
REFRAIN = [
    "Bonjour la ferme, bonjour, bonjour !",
    "Les animaux chantent tout autour !",
    "Meuh, coin-coin, groin-groin, bê-bê,",
    "On tape des mains, on tape des pieds !",
]
PONT = [
    "La lune brille, il fait tout noir,",
    "Les animaux disent bonsoir.",
    "Le mouton fait un doux bê-bê,",
    "Chut… tout le monde va rêver.",
]


@dataclass
class Ligne:
    texte: str
    section: str
    type_section: str
    mesure: int              # mesure de départ
    gabarit: list            # une hauteur MIDI par croche
    slots: int               # nombre de doubles croches disponibles pour chanter
    decalage: int = 0        # décalage en doubles croches depuis le début de la mesure
    transpo: int = 0
    style: str = "chant"     # "chant" ou "cri" (interjection courte)
    syllabes: list = field(default_factory=list)
    notes: list = None       # facultatif : une hauteur MIDI par syllabe (remplace le gabarit)
    durees: list = None      # facultatif : durée de chaque syllabe en doubles croches


def construire_lignes():
    """Renvoie la liste ordonnée des lignes chantées avec leur placement."""
    lignes = []
    for nom, typ, m0, nb, _decor, tr in SECTIONS:
        if typ == "intro":
            lignes.append(Ligne("Cocorico !", nom, typ, m0 + 3, G["cocorico"], 8,
                                style="cri"))
        elif typ == "couplet":
            for i, txt in enumerate(COUPLETS[nom]):
                lignes.append(Ligne(txt, nom, typ, m0 + 2 * i, G[f"c{i + 1}"], 28))
        elif typ in ("refrain", "final"):
            for i, txt in enumerate(REFRAIN):
                slots = 28
                if typ == "final" and tr == 0 and i == 3:
                    slots = 24          # on laisse la place à « Encore une fois ! »
                lignes.append(Ligne(txt, nom, typ, m0 + 2 * i, G[f"r{i + 1}"], slots,
                                    transpo=tr))
            if typ == "final" and tr == 0:
                lignes.append(Ligne("Encore une fois !", nom, typ, m0 + 7,
                                    G["encore"], 8, decalage=8, style="cri"))
        elif typ == "pont":
            # 5 mesures : une ligne douce par mesure, puis 1 mesure de respiration
            for i, txt in enumerate(PONT):
                lignes.append(Ligne(txt, nom, typ, m0 + i, G[f"p{i + 1}"], 16))
        elif typ == "outro":
            lignes.append(Ligne("Au revoir les amis !", nom, typ, m0 + 1, G["aurevoir"], 24))
    return lignes


def accords_par_mesure():
    """Liste (longueur NB_MESURES) de (accord, transposition, type_section)."""
    res = []
    for nom, typ, m0, nb, _decor, tr in SECTIONS:
        acc = ACCORDS_SECTION[typ]
        for k in range(nb):
            res.append((acc[k % len(acc)], tr, typ))
    return res


def section_a(t, mesure_s):
    """Section active à l'instant t (secondes)."""
    m = t / mesure_s
    cur = SECTIONS[0]
    for s in SECTIONS:
        if m >= s[2]:
            cur = s
    return cur

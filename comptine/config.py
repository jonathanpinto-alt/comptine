"""Constantes globales du projet."""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ASSETS = RACINE / "assets"
SORTIE = RACINE / "sortie"
TMP = SORTIE / "tmp"
POLICE = ASSETS / "fonts" / "Fredoka.ttf"
SOUNDFONT_CANDIDATS = [
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    Path("/usr/share/sounds/sf2/default-GM.sf2"),
    Path("/usr/share/soundfonts/FluidR3_GM.sf2"),
    Path("/usr/share/soundfonts/default.sf2"),
]

BPM = 110
TEMPS_PAR_MESURE = 4
NOIRE = 60.0 / BPM                      # durée d'un temps (s)
CROCHE = NOIRE / 2
DOUBLE = NOIRE / 4                      # unité de la grille rythmique (double croche)
MESURE = NOIRE * TEMPS_PAR_MESURE
NB_MESURES = 69
DUREE_TOTALE = NB_MESURES * MESURE      # ≈ 150,5 s

SR = 44100
LARGEUR, HAUTEUR, FPS = 1920, 1080, 30

DUREE_MIN, DUREE_MAX = 145.0, 155.0     # 2 min 25 – 2 min 35

# Palette tournante des sous-titres (rouge, orange, jaune, vert, bleu, violet, rose)
PALETTE = [
    (255, 59, 59),
    (255, 145, 30),
    (255, 214, 0),
    (60, 200, 70),
    (40, 140, 255),
    (160, 80, 230),
    (255, 90, 180),
]

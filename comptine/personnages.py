"""Personnages en SVG (formes rondes, gros yeux) + rastérisation en sprites.

Chaque animal existe en 3 états : « normal », « cligne » (yeux fermés) et
« chante » (bouche ouverte). Les SVG sont écrits dans assets/personnages/ puis
convertis en PNG (cairosvg) ; l'animation (rebond, écrasement, rotation) est
faite au rendu par transformations affines.
"""
import io

import cairo
import cairosvg

from . import config as C

TRAIT = "#4a2f2a"
TAILLE_SPRITE = 520          # px (le viewBox fait 400x400)


# ------------------------------------------------------------------ éléments
def yeux(x1, x2, y, r=30, etat="normal", couleur_trait=TRAIT):
    if etat == "cligne":
        def arc(x):
            return (f'<path d="M{x - r * 0.8},{y} Q{x},{y + r * 0.9} {x + r * 0.8},{y}" '
                    f'fill="none" stroke="{couleur_trait}" stroke-width="7" stroke-linecap="round"/>')
        return arc(x1) + arc(x2)
    s = ""
    for x in (x1, x2):
        s += (f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" stroke="{couleur_trait}" stroke-width="4"/>'
              f'<circle cx="{x + 3}" cy="{y + 4}" r="{r * 0.62}" fill="#2b1d1d"/>'
              f'<circle cx="{x + 3}" cy="{y + 4}" r="{r * 0.62}" fill="url(#iris)"/>'
              f'<circle cx="{x + r * 0.25}" cy="{y - r * 0.18}" r="{r * 0.24}" fill="#fff"/>'
              f'<circle cx="{x - r * 0.15}" cy="{y + r * 0.3}" r="{r * 0.11}" fill="#fff"/>')
    return s


def bouche(x, y, etat, l=30):
    if etat == "chante":
        return (f'<ellipse cx="{x}" cy="{y + 8}" rx="{l * 0.7}" ry="{l * 0.75}" fill="#7a1f2b" '
                f'stroke="{TRAIT}" stroke-width="4"/>'
                f'<ellipse cx="{x}" cy="{y + 8 + l * 0.38}" rx="{l * 0.45}" ry="{l * 0.3}" fill="#ff7b93"/>')
    return (f'<path d="M{x - l},{y} Q{x},{y + l * 0.9} {x + l},{y}" fill="none" '
            f'stroke="{TRAIT}" stroke-width="6" stroke-linecap="round"/>')


def joues(x1, x2, y, r=17, c="#ff8fab"):
    return (f'<ellipse cx="{x1}" cy="{y}" rx="{r}" ry="{r * 0.7}" fill="{c}" opacity="0.6"/>'
            f'<ellipse cx="{x2}" cy="{y}" rx="{r}" ry="{r * 0.7}" fill="{c}" opacity="0.6"/>')


def bec(x, y, etat, c="#ffb300", w=34, h=22):
    if etat == "chante":
        return (f'<path d="M{x - w / 2},{y - 4} Q{x},{y - h - 6} {x + w / 2},{y - 4} Z" fill="{c}" stroke="{TRAIT}" stroke-width="4" stroke-linejoin="round"/>'
                f'<path d="M{x - w / 2 + 3},{y + 6} Q{x},{y + h + 4} {x + w / 2 - 3},{y + 6} Z" fill="{c}" stroke="{TRAIT}" stroke-width="4" stroke-linejoin="round"/>'
                f'<ellipse cx="{x}" cy="{y + 1}" rx="{w * 0.32}" ry="5" fill="#7a1f2b"/>')
    return (f'<path d="M{x - w / 2},{y - 2} Q{x},{y - h} {x + w / 2},{y - 2} Q{x},{y + h} {x - w / 2},{y - 2} Z" '
            f'fill="{c}" stroke="{TRAIT}" stroke-width="4" stroke-linejoin="round"/>')


DEFS = ('<defs>'
        '<radialGradient id="iris" cx="0.4" cy="0.35" r="0.7">'
        '<stop offset="0" stop-color="#6b4a3a"/><stop offset="1" stop-color="#1b1010"/></radialGradient>'
        '<radialGradient id="ombre" cx="0.5" cy="0.5" r="0.5">'
        '<stop offset="0" stop-color="#000" stop-opacity="0.25"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>'
        '</defs>')


def svg(contenu):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" '
            f'width="{TAILLE_SPRITE}" height="{TAILLE_SPRITE}">{DEFS}{contenu}</svg>')


def pattes(xs, y0, y1, c, w=34):
    return "".join(f'<rect x="{x - w / 2}" y="{y0}" width="{w}" height="{y1 - y0}" rx="{w / 2}" '
                   f'fill="{c}" stroke="{TRAIT}" stroke-width="4"/>' for x in xs)


# ------------------------------------------------------------------ animaux
def vache(e):
    b, tache, rose = "#ffffff", "#5b3a2e", "#ffb3c6"
    return svg(
        pattes([135, 180, 225, 270], 320, 392, b) +
        pattes([135, 180, 225, 270], 372, 392, "#5b3a2e") +
        f'<ellipse cx="200" cy="300" rx="125" ry="70" fill="{b}" stroke="{TRAIT}" stroke-width="5"/>'
        f'<ellipse cx="150" cy="290" rx="35" ry="25" fill="{tache}"/>'
        f'<ellipse cx="265" cy="315" rx="28" ry="20" fill="{tache}"/>'
        f'<path d="M322,290 Q360,270 352,240" fill="none" stroke="{TRAIT}" stroke-width="6" stroke-linecap="round"/>'
        f'<circle cx="352" cy="236" r="12" fill="{tache}"/>'
        # cornes et oreilles
        f'<path d="M135,75 Q120,40 140,30 Q150,55 158,72 Z" fill="#ffe08a" stroke="{TRAIT}" stroke-width="4"/>'
        f'<path d="M265,75 Q280,40 260,30 Q250,55 242,72 Z" fill="#ffe08a" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="80" cy="120" rx="42" ry="22" transform="rotate(-20 80 120)" fill="{b}" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="82" cy="121" rx="26" ry="11" transform="rotate(-20 80 120)" fill="{rose}"/>'
        f'<ellipse cx="320" cy="120" rx="42" ry="22" transform="rotate(20 320 120)" fill="{b}" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="318" cy="121" rx="26" ry="11" transform="rotate(20 320 120)" fill="{rose}"/>'
        # tête
        f'<ellipse cx="200" cy="150" rx="112" ry="100" fill="{b}" stroke="{TRAIT}" stroke-width="5"/>'
        f'<ellipse cx="265" cy="95" rx="30" ry="22" fill="{tache}"/>'
        f'<ellipse cx="200" cy="208" rx="80" ry="46" fill="{rose}" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="175" cy="198" rx="9" ry="12" fill="#c2607a"/>'
        f'<ellipse cx="225" cy="198" rx="9" ry="12" fill="#c2607a"/>'
        + yeux(160, 240, 138, 30, "cligne" if e == "cligne" else "normal") +
        joues(115, 285, 175) + bouche(200, 225, e, 24))


def coq(e):
    return svg(
        pattes([170, 230], 320, 390, "#ffb300", 16) +
        # queue
        f'<ellipse cx="320" cy="200" rx="30" ry="70" transform="rotate(25 320 200)" fill="#2e9e5b" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="335" cy="230" rx="28" ry="62" transform="rotate(45 335 230)" fill="#2c6fd6" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="300" cy="185" rx="24" ry="60" transform="rotate(5 300 185)" fill="#e53935" stroke="{TRAIT}" stroke-width="4"/>'
        # corps
        f'<ellipse cx="200" cy="245" rx="120" ry="100" fill="#ffffff" stroke="{TRAIT}" stroke-width="5"/>'
        f'<ellipse cx="240" cy="260" rx="55" ry="40" transform="rotate(-15 240 260)" fill="#ffd8a8" stroke="{TRAIT}" stroke-width="4"/>'
        # crête
        f'<circle cx="160" cy="70" r="26" fill="#e53935" stroke="{TRAIT}" stroke-width="4"/>'
        f'<circle cx="195" cy="58" r="30" fill="#e53935" stroke="{TRAIT}" stroke-width="4"/>'
        f'<circle cx="232" cy="70" r="26" fill="#e53935" stroke="{TRAIT}" stroke-width="4"/>'
        # tête (fondue dans le corps)
        f'<circle cx="195" cy="150" r="82" fill="#ffffff" stroke="{TRAIT}" stroke-width="5"/>'
        f'<ellipse cx="195" cy="222" rx="18" ry="24" fill="#e53935" stroke="{TRAIT}" stroke-width="4"/>'
        + yeux(165, 225, 140, 24, "cligne" if e == "cligne" else "normal") +
        joues(140, 250, 175, 13) + bec(195, 185, e, w=40, h=24))


def canard(e):
    return svg(
        f'<ellipse cx="200" cy="380" rx="70" ry="12" fill="#ff9800" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="210" cy="285" rx="140" ry="92" fill="#ffe14d" stroke="{TRAIT}" stroke-width="5"/>'
        f'<path d="M340,250 Q385,220 370,270 Z" fill="#ffe14d" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="250" cy="285" rx="60" ry="38" transform="rotate(-12 250 285)" fill="#ffd21a" stroke="{TRAIT}" stroke-width="4"/>'
        f'<circle cx="170" cy="150" r="95" fill="#ffe14d" stroke="{TRAIT}" stroke-width="5"/>'
        f'<path d="M160,58 Q170,25 185,50 Q195,30 200,62" fill="#ffe14d" stroke="{TRAIT}" stroke-width="4"/>'
        + yeux(135, 205, 135, 28, "cligne" if e == "cligne" else "normal") +
        joues(105, 235, 175, 14) +
        (f'<ellipse cx="170" cy="195" rx="56" ry="20" fill="#ff9800" stroke="{TRAIT}" stroke-width="4"/>'
         if e != "chante" else
         f'<ellipse cx="170" cy="188" rx="56" ry="18" fill="#ff9800" stroke="{TRAIT}" stroke-width="4"/>'
         f'<ellipse cx="170" cy="212" rx="44" ry="14" fill="#ff9800" stroke="{TRAIT}" stroke-width="4"/>'
         f'<ellipse cx="170" cy="200" rx="34" ry="7" fill="#7a1f2b"/>'))


def cochon(e):
    r, rf = "#ffadc6", "#ff8fb1"
    return svg(
        pattes([140, 185, 225, 270], 320, 392, r) +
        f'<ellipse cx="205" cy="290" rx="135" ry="78" fill="{r}" stroke="{TRAIT}" stroke-width="5"/>'
        f'<path d="M338,280 q25,-10 18,-28 q-8,-14 -20,0 q-8,15 12,22" fill="none" stroke="{TRAIT}" stroke-width="6" stroke-linecap="round"/>'
        f'<path d="M95,95 L70,30 L140,70 Z" fill="{rf}" stroke="{TRAIT}" stroke-width="4" stroke-linejoin="round"/>'
        f'<path d="M305,95 L330,30 L260,70 Z" fill="{rf}" stroke="{TRAIT}" stroke-width="4" stroke-linejoin="round"/>'
        f'<ellipse cx="200" cy="160" rx="118" ry="102" fill="{r}" stroke="{TRAIT}" stroke-width="5"/>'
        f'<ellipse cx="200" cy="185" rx="50" ry="36" fill="{rf}" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="183" cy="185" rx="9" ry="14" fill="#b84d6e"/>'
        f'<ellipse cx="217" cy="185" rx="9" ry="14" fill="#b84d6e"/>'
        + yeux(150, 250, 128, 28, "cligne" if e == "cligne" else "normal") +
        joues(110, 290, 175, 18, "#ff6f91") + bouche(200, 232, e, 24))


def mouton(e):
    laine = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#ffffff" stroke="#d9d4e6" stroke-width="4"/>'
                    for x, y, r in [(90, 270, 55), (140, 220, 60), (210, 205, 62), (280, 225, 58),
                                    (320, 280, 52), (270, 330, 55), (190, 335, 58), (115, 320, 52),
                                    (200, 270, 80)])
    return svg(
        pattes([140, 180, 230, 270], 330, 392, "#5d5470", 26) + laine +
        f'<ellipse cx="95" cy="150" rx="40" ry="18" transform="rotate(-25 95 150)" fill="#5d5470"/>'
        f'<ellipse cx="305" cy="150" rx="40" ry="18" transform="rotate(25 305 150)" fill="#5d5470"/>'
        f'<ellipse cx="200" cy="165" rx="92" ry="98" fill="#6b6280" stroke="{TRAIT}" stroke-width="4"/>'
        + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#ffffff" stroke="#d9d4e6" stroke-width="4"/>'
                  for x, y, r in [(150, 75, 32), (200, 62, 36), (250, 75, 32)]) +
        yeux(165, 235, 160, 26, "cligne" if e == "cligne" else "normal", "#2b2238") +
        joues(130, 270, 200, 14) + bouche(200, 215, e, 20))


def cheval(e):
    c, cr, m = "#c98b5a", "#f2cfa8", "#6b3b22"
    return svg(
        pattes([140, 185, 230, 275], 310, 392, c, 30) +
        pattes([140, 185, 230, 275], 372, 392, "#4a2f2a", 30) +
        f'<ellipse cx="210" cy="285" rx="125" ry="70" fill="{c}" stroke="{TRAIT}" stroke-width="5"/>'
        f'<path d="M330,270 Q380,280 365,340 Q345,300 325,295 Z" fill="{m}" stroke="{TRAIT}" stroke-width="4"/>'
        # oreilles
        f'<ellipse cx="140" cy="55" rx="18" ry="38" transform="rotate(-15 140 55)" fill="{c}" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="250" cy="55" rx="18" ry="38" transform="rotate(15 250 55)" fill="{c}" stroke="{TRAIT}" stroke-width="4"/>'
        # tête
        f'<ellipse cx="195" cy="150" rx="95" ry="100" fill="{c}" stroke="{TRAIT}" stroke-width="5"/>'
        + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{m}" stroke="{TRAIT}" stroke-width="3"/>'
                  for x, y, r in [(165, 62, 26), (200, 52, 28), (235, 62, 24), (275, 95, 26), (290, 135, 24)]) +
        f'<ellipse cx="195" cy="215" rx="72" ry="48" fill="{cr}" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="170" cy="205" rx="8" ry="11" fill="#8a5a3a"/>'
        f'<ellipse cx="220" cy="205" rx="8" ry="11" fill="#8a5a3a"/>'
        + yeux(160, 235, 130, 27, "cligne" if e == "cligne" else "normal") +
        joues(118, 272, 170, 14) + bouche(195, 230, e, 22))


def poussin(e):
    return svg(
        pattes([170, 230], 335, 390, "#ff9800", 14) +
        f'<circle cx="200" cy="235" r="135" fill="#ffeb3b" stroke="{TRAIT}" stroke-width="5"/>'
        f'<path d="M185,105 Q190,70 205,98 Q215,72 220,108" fill="#ffeb3b" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="80" cy="250" rx="30" ry="50" transform="rotate(25 80 250)" fill="#fdd835" stroke="{TRAIT}" stroke-width="4"/>'
        f'<ellipse cx="320" cy="250" rx="30" ry="50" transform="rotate(-25 320 250)" fill="#fdd835" stroke="{TRAIT}" stroke-width="4"/>'
        + yeux(160, 240, 205, 32, "cligne" if e == "cligne" else "normal") +
        joues(120, 280, 255, 18) + bec(200, 255, e, "#ff9800", 40, 24))


ANIMAUX = {"vache": vache, "coq": coq, "canard": canard, "cochon": cochon,
           "mouton": mouton, "cheval": cheval, "poussin": poussin}
ETATS = ("normal", "cligne", "chante")


def generer_svg():
    """Écrit les fichiers SVG dans assets/personnages/ et renvoie {(animal, etat): svg}."""
    dossier = C.ASSETS / "personnages"
    dossier.mkdir(parents=True, exist_ok=True)
    res = {}
    for nom, f in ANIMAUX.items():
        for e in ETATS:
            code = f(e)
            (dossier / f"{nom}_{e}.svg").write_text(code, encoding="utf-8")
            res[(nom, e)] = code
    return res


def charger_sprites():
    """{(animal, etat): cairo.ImageSurface} rastérisés depuis les SVG."""
    sprites = {}
    for (nom, e), code in generer_svg().items():
        png = cairosvg.svg2png(bytestring=code.encode("utf-8"),
                               output_width=TAILLE_SPRITE, output_height=TAILLE_SPRITE)
        sprites[(nom, e)] = cairo.ImageSurface.create_from_png(io.BytesIO(png))
    return sprites

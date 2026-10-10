"""Composition des éléments 3D pré-rendus (Blender) en images animées.

Ordre des plans : ciel en dégradé animé → astres et nuages 3D → décor 3D
(léger travelling de caméra) → personnages 3D → effets de premier plan.
"""
import json
import math
import random

import cairo

from . import config as C
from . import decors as D

DOSSIER = C.ASSETS / "rendus3d"
W, H = C.LARGEUR, C.HAUTEUR
G3 = {}

CIELS = {   # (haut, bas) des dégradés pastel animés
    "aube": (("#ffb6a3", "#9fd8ff"), ("#ffe5b4", "#e3f6ff")),
    "pre": (("#8fd3ff", "#a9ddff"), ("#e6f7ff", "#fff6e8")),
    "grange": (("#ffc1e3", "#a5dcff"), ("#fff3c4", "#ffe0f0")),
    "mare": (("#9ee6ff", "#b5e9ff"), ("#eafff5", "#fff6e0")),
    "nuit": (("#1a1446", "#2a1d5c"), ("#5b3f8c", "#4a3a8a")),
    "foret": (("#ffd1dc", "#a6e3ff"), ("#fff1c1", "#f0fff0")),
    "fete": (("#a5dcff", "#ffc6ec"), ("#fff6c9", "#e0ffe8")),
    "couchant": (("#ff9a8b", "#8e6bbf"), ("#ffd194", "#ff9ab0")),
}


def charger():
    """Charge sprites, décors et accessoires 3D (une fois par processus)."""
    if G3:
        return G3
    for cat in ("persos", "decors", "accessoires"):
        if not (DOSSIER / cat).exists():
            raise SystemExit(f"Rendus 3D absents ({DOSSIER / cat}) : lancer d'abord le rendu Blender.")
    G3["meta"] = json.loads((DOSSIER / "persos" / "persos.json").read_text())
    G3["persos"] = {}
    for f in (DOSSIER / "persos").glob("*.png"):
        nom, etat = f.stem.split("_")
        G3["persos"][(nom, etat)] = cairo.ImageSurface.create_from_png(str(f))
    G3["decors"] = {f.stem[6:]: cairo.ImageSurface.create_from_png(str(f)) for f in (DOSSIER / "decors").glob("decor_*.png")}
    G3["acc"] = {f.stem: cairo.ImageSurface.create_from_png(str(f)) for f in (DOSSIER / "accessoires").glob("*.png")}
    return G3


def sprite(ctx, surf, x, y, largeur, rot=0.0, alpha=1.0, ancre=(0.5, 0.5), flip=False, sy=1.0):
    k = largeur / surf.get_width()
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(k * (-1 if flip else 1), k * sy)
    ctx.set_source_surface(surf, -surf.get_width() * ancre[0], -surf.get_height() * ancre[1])
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def ciel(ctx, decor, t, tl):
    (h1, h2), (b1, b2) = CIELS[decor]
    if decor in ("aube", "couchant", "foret"):
        a = min(1.0, tl / (8.7 if decor != "foret" else 4.0))
    else:
        a = 0.5 + 0.5 * math.sin(t * 0.45)
    D.ciel(ctx, D.melange(D.rgb(h1), D.rgb(h2), a), D.melange(D.rgb(b1), D.rgb(b2), a))


def nuages(ctx, t, n=5, graine=3, vitesse=22, alpha=1.0, y0=90, y1=330):
    acc = G3["acc"]
    rnd = random.Random(graine)
    for k in range(n):
        larg = rnd.uniform(260, 430)
        y = rnd.uniform(y0, y1)
        x0 = rnd.uniform(0, W + 600)
        v = vitesse * rnd.uniform(0.6, 1.3)
        x = (x0 + t * v) % (W + 600) - 300
        sprite(ctx, acc[f"nuage{k % 3 + 1}"], x, y + 6 * math.sin(t * 0.8 + k), larg, alpha=alpha)


def etoiles(ctx, t, n=45, graine=7, y_max=520, alpha=1.0):
    rnd = random.Random(graine)
    for k in range(n):
        x, y = rnd.uniform(20, W - 20), rnd.uniform(20, y_max)
        r = rnd.uniform(26, 62)
        sc = 0.6 + 0.4 * math.sin(t * rnd.uniform(1.5, 3.5) + rnd.uniform(0, 6.28))
        sprite(ctx, G3["acc"]["etoile"], x, y, r * sc, rot=0.25 * math.sin(t + k), alpha=alpha * (0.5 + 0.5 * sc))


def arriere_plan(ctx, decor, t, tl, tr):
    """Ciel, astres et nuages (derrière le décor 3D)."""
    acc = G3["acc"]
    ciel(ctx, decor, t, tl)
    bal = 0.06 * math.sin(t * 1.3)
    if decor == "aube":
        p = min(1.0, tl / 7.5)
        sprite(ctx, acc["soleil"], 1500, 640 - 450 * (1 - (1 - p) ** 2), 330, rot=bal)
        nuages(ctx, t, 4, graine=1)
    elif decor in ("pre", "grange", "mare", "fete"):
        pos = {"pre": (300, 200), "grange": (1650, 185), "mare": (1680, 175), "fete": (1720, 170)}[decor]
        sprite(ctx, acc["soleil"], pos[0], pos[1] + 6 * math.sin(t * 2), 300, rot=bal)
        nuages(ctx, t, 5, graine={"pre": 2, "grange": 4, "mare": 6, "fete": 12}[decor],
               vitesse=40 if decor == "fete" else 22)
    elif decor == "nuit":
        etoiles(ctx, t)
        sprite(ctx, acc["lune"], 1500, 240 + 8 * math.sin(t * 0.9), 270, rot=0.05 * math.sin(t * 0.7))
        nuages(ctx, t, 3, graine=8, vitesse=10, alpha=0.35)
    elif decor == "foret":
        p = min(1.0, tl / 4)
        sprite(ctx, acc["soleil"], 960, 360 - 170 * p, 300, rot=bal)
        nuages(ctx, t, 4, graine=10)
    elif decor == "couchant":
        p = min(1.0, tl / 8.7)
        etoiles(ctx, t, n=20, y_max=330, alpha=p)
        sprite(ctx, acc["soleil"], 960, 470 + 330 * p, 340, rot=bal)
        nuages(ctx, t, 4, graine=14, vitesse=14, alpha=0.8)


def camera(ctx, decor, tl, duree):
    """Léger travelling avant (effet de profondeur) appliqué au décor et aux personnages."""
    u = min(1.0, max(0.0, tl / max(duree, 1e-3)))
    z = 1.0 + 0.045 * u
    dx = {"foret": -25, "mare": 20}.get(decor, 0) * u
    ctx.translate(W / 2 + dx, H * 0.78)
    ctx.scale(z, z)
    ctx.translate(-W / 2, -H * 0.78)


def decor(ctx, nom):
    ctx.set_source_surface(G3["decors"][nom], 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()


def premier_plan(ctx, decor_nom, t, tl, tr):
    if decor_nom == "fete":
        rnd = random.Random(5)
        couleurs = ["ff5252", "ffa726", "ffee58", "66bb6a", "42a5f5", "ab47bc", "ff80ab"]
        for k in range(8):
            x0 = rnd.uniform(80, W - 80)
            v = rnd.uniform(60, 100)
            ph = rnd.uniform(0, H + 500)
            y = H + 250 - (ph + t * v) % (H + 500)
            x = x0 + 25 * math.sin(t * 1.2 + k)
            ctx.set_source_rgba(0.45, 0.45, 0.5, 0.7)
            ctx.set_line_width(2.5)
            ctx.move_to(x, y + 70)
            ctx.curve_to(x + 12, y + 110, x - 12, y + 150, x, y + 200)
            ctx.stroke()
            sprite(ctx, G3["acc"]["ballon_" + couleurs[k % 7]], x, y, 150, rot=0.08 * math.sin(t * 1.5 + k))
        D.fanions(ctx, t)
        D.confettis(ctx, t, intensite=1.3 if tr else 1.0)
    elif decor_nom == "grange":
        rnd = random.Random(13)
        for k in range(8):
            x0 = rnd.uniform(100, W - 100)
            ph = (t * 0.25 + k / 8) % 1
            D.note_musique(ctx, x0 + 40 * math.sin(ph * 12.6 + k), 700 - ph * 620, 30,
                           D.rgb(["#ff5252", "#42a5f5", "#ab47bc", "#ffa726", "#66bb6a"][k % 5]),
                           alpha=math.sin(ph * math.pi))
    elif decor_nom == "nuit":
        D.lucioles(ctx, t)

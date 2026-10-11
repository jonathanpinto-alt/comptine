"""Animation de « C'est l'heure du bain » : composition des rendus 3D image par image.

Pour chaque image : plan (décor 3D) → garçon (sprite 3D de la pose et de
l'expression du moment, cadré par le holdout) → effets (bulles, éclaboussures,
canard, miroirs avec reflet, étincelles) → travelling de caméra → karaoké.
Le montage suit l'ordre demandé : 1, 2, 3, 4, 5, 3, 4, 3, 4, 5, 6, 6, 3, 4, 5, 7
(deux scènes par section, transition « bulle » entre les plans).
"""
import json
import math
import random
from functools import lru_cache

import cairo
import numpy as np
from PIL import Image, ImageDraw

from .. import config as C
from .. import rendu as R
from . import chanson as B
from .rendu3d import DOSSIER

W, H = C.LARGEUR, C.HAUTEUR
TRANSITION = 0.5
G3 = {}


# ======================================================================= chargement
def charger():
    if G3:
        return G3
    if not (DOSSIER / "garcon" / "decoupes.json").exists():
        raise SystemExit(f"Rendus 3D absents ({DOSSIER}) : lancer d'abord le rendu Blender.")
    G3["plans"] = {f.stem[5:]: cairo.ImageSurface.create_from_png(str(f))
                   for f in (DOSSIER / "plans").glob("plan_*.png")}
    G3["plans_meta"] = json.loads((DOSSIER / "plans" / "plans.json").read_text())
    dec = json.loads((DOSSIER / "garcon" / "decoupes.json").read_text())
    G3["garcon"] = {}
    for nom, (x0, y0) in dec.items():
        pose, expr = nom[:-4].split("__")
        G3["garcon"][(pose, expr)] = (cairo.ImageSurface.create_from_png(str(DOSSIER / "garcon" / nom)), x0, y0)
    G3["meta"] = {}
    for f in (DOSSIER / "garcon").glob("meta_*.json"):
        G3["meta"].update(json.loads(f.read_text()))
    G3["acc"] = {f.stem: cairo.ImageSurface.create_from_png(str(f)) for f in (DOSSIER / "accessoires").glob("*.png")}
    return G3


def init_worker(donnees, echelle):
    R.G["d"] = donnees
    R.G["echelle"] = echelle
    charger()
    G3["plans_montage"] = B.plan_de_montage(C.MESURE)
    G3["mots"] = donnees["mots"]


preparer_donnees = R.preparer_donnees


# ======================================================================= outils de dessin
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def garcon(ctx, pose, expr, dx=0.0, dy=0.0, sx=1.0, sy=1.0, ancre=None, rot=0.0, alpha=1.0, flip=False):
    """Dessine le sprite (pose, expression) à sa place dans le cadre, avec une petite
    transformation 2D autour de `ancre` (pieds par défaut)."""
    cle = (pose, expr)
    if cle not in G3["garcon"]:
        cle = (pose, next(e for p, e in G3["garcon"] if p == pose))
    surf, x0, y0 = G3["garcon"][cle]
    ax, ay = ancre or G3["meta"][pose]["pieds"]
    ctx.save()
    ctx.translate(ax + dx, ay + dy)
    ctx.rotate(rot)
    ctx.scale(sx * (-1 if flip else 1), sy)
    ctx.translate(-ax, -ay)
    ctx.set_source_surface(surf, x0, y0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def sprite(ctx, surf, x, y, largeur, rot=0.0, alpha=1.0, flip=False, ancre=(0.5, 0.5)):
    k = largeur / surf.get_width()
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.scale(k * (-1 if flip else 1), k)
    ctx.set_source_surface(surf, -surf.get_width() * ancre[0], -surf.get_height() * ancre[1])
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint_with_alpha(alpha)
    ctx.restore()


def ombre(ctx, x, y, rx, ry, alpha=0.28):
    g = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
    g.add_color_stop_rgba(0, 0.25, 0.2, 0.35, alpha)
    g.add_color_stop_rgba(1, 0.25, 0.2, 0.35, 0.0)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(rx, ry)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.set_source(g)
    ctx.fill()
    ctx.restore()


TEINTES = [(1.0, 0.6, 0.85), (0.55, 0.85, 1.0), (0.75, 0.65, 1.0), (1.0, 0.9, 0.5), (0.6, 1.0, 0.8)]


def bulle(ctx, x, y, r, alpha=1.0, teinte=0, eclat=0.0):
    """Bulle de savon : intérieur presque transparent, bord irisé, reflets.
    `eclat` (0..1) : la bulle qui éclate grossit et s'efface."""
    if eclat > 0:
        r *= 1 + 0.35 * eclat
        alpha *= 1 - eclat
    if alpha <= 0.01 or r < 1:
        return
    c = TEINTES[teinte % len(TEINTES)]
    g = cairo.RadialGradient(x - r * 0.25, y - r * 0.3, r * 0.1, x, y, r)
    g.add_color_stop_rgba(0, 1, 1, 1, 0.10 * alpha)
    g.add_color_stop_rgba(0.75, c[0], c[1], c[2], 0.12 * alpha)
    g.add_color_stop_rgba(0.93, c[0], c[1], c[2], 0.55 * alpha)
    g.add_color_stop_rgba(1, 1, 1, 1, 0.75 * alpha)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.set_source(g)
    ctx.fill()
    # bord irisé (deux arcs colorés)
    ctx.set_line_width(max(1.5, r * 0.05))
    for k, (a0, a1, col) in enumerate(((0.6, 1.9, (1.0, 0.55, 0.85)), (3.6, 4.9, (0.5, 0.85, 1.0)))):
        ctx.arc(x, y, r * 0.96, a0, a1)
        ctx.set_source_rgba(*col, 0.55 * alpha)
        ctx.stroke()
    # reflets
    ctx.save()
    ctx.translate(x - r * 0.38, y - r * 0.42)
    ctx.rotate(-0.6)
    ctx.scale(r * 0.26, r * 0.13)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.set_source_rgba(1, 1, 1, 0.85 * alpha)
    ctx.fill()
    ctx.arc(x + r * 0.42, y + r * 0.4, r * 0.08, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 1, 1, 0.6 * alpha)
    ctx.fill()


def bulles_montantes(ctx, t, zone, n=14, graine=1, vitesse=60, r=(14, 42), alpha=1.0):
    """Bulles qui montent en ondulant depuis une zone (x0, x1, y_bas) et éclatent en haut."""
    x0, x1, yb = zone
    rnd = random.Random(graine)
    hauteur = yb + 80
    for k in range(n):
        rr = rnd.uniform(*r)
        v = vitesse * rnd.uniform(0.6, 1.4)
        ph = rnd.uniform(0, hauteur)
        course = (ph + t * v) % hauteur
        y = yb - course
        x = rnd.uniform(x0, x1) + 30 * math.sin(t * rnd.uniform(0.8, 1.6) + k)
        fin = course / hauteur
        eclat = max(0.0, (fin - 0.9) / 0.1)
        bulle(ctx, x, y, rr, alpha * min(1.0, course / 60), teinte=k, eclat=eclat)


def goutte(ctx, x, y, r, angle, alpha=1.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(angle)
    ctx.move_to(0, -r * 1.9)
    ctx.curve_to(r * 0.9, -r * 0.6, r, r * 0.9, 0, r)
    ctx.curve_to(-r, r * 0.9, -r * 0.9, -r * 0.6, 0, -r * 1.9)
    ctx.set_source_rgba(0.45, 0.78, 1.0, 0.85 * alpha)
    ctx.fill_preserve()
    ctx.set_source_rgba(1, 1, 1, 0.9 * alpha)
    ctx.set_line_width(max(1.0, r * 0.15))
    ctx.stroke()
    ctx.arc(-r * 0.3, r * 0.1, r * 0.25, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 1, 1, 0.9 * alpha)
    ctx.fill()
    ctx.restore()


def eclaboussure(ctx, x, y, u, graine, n=12, force=1.0):
    """Gerbe de gouttes (u = temps écoulé depuis l'impact, en s)."""
    if u < 0 or u > 0.9:
        return
    rnd = random.Random(graine)
    for k in range(n):
        a = -math.pi / 2 + rnd.uniform(-1.1, 1.1)
        v = rnd.uniform(380, 720) * force
        gx = x + math.cos(a) * v * u
        gy = y + math.sin(a) * v * u + 0.5 * 1500 * u * u
        vy = math.sin(a) * v + 1500 * u
        vx = math.cos(a) * v
        goutte(ctx, gx, gy, rnd.uniform(7, 14) * force, math.atan2(vy, vx) - math.pi / 2, 1 - u / 0.9)


def etincelle(ctx, x, y, r, alpha=1.0, couleur=(1.0, 0.95, 0.55)):
    """Petite étoile scintillante à 4 branches (côtés incurvés)."""
    if alpha <= 0.01 or r <= 0.5:
        return
    ctx.save()
    ctx.translate(x, y)
    pts = [(0, -r), (r, 0), (0, r), (-r, 0)]
    ctx.move_to(*pts[0])
    for k in range(4):
        x2, y2 = pts[(k + 1) % 4]
        ctx.curve_to(0, 0, 0, 0, x2, y2)
    ctx.close_path()
    ctx.set_source_rgba(*couleur, alpha)
    ctx.fill()
    ctx.arc(0, 0, r * 0.18, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 1, 1, alpha)
    ctx.fill()
    ctx.restore()


def etincelles(ctx, t, cx, cy, rayon, n=8, graine=3, alpha=1.0):
    rnd = random.Random(graine)
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        d = rayon * rnd.uniform(0.5, 1.0)
        ph = (t * rnd.uniform(0.8, 1.5) + rnd.uniform(0, 1)) % 1
        etincelle(ctx, cx + d * math.cos(a), cy + d * math.sin(a), rnd.uniform(14, 30) * math.sin(math.pi * ph),
                  alpha * math.sin(math.pi * ph), couleur=[(1, 0.95, 0.5), (1, 1, 1), (0.7, 0.9, 1)][k % 3])


def canard(ctx, t, x, y, largeur, flip=False, graine=0):
    rot = 0.08 * math.sin(t * 2.3 + graine)
    sprite(ctx, G3["acc"]["canard"], x, y + 6 * math.sin(t * 2.3 + graine + 0.6), largeur, rot=rot, flip=flip,
           ancre=(0.5, 0.62))


# ======================================================================= temps musicaux
def battue(t):
    return (t / C.NOIRE) % 1.0


@lru_cache(maxsize=None)
def instants(mot, section=None):
    res = []
    for la in R.G["d"]["lignes"]:
        if section and la["section"] != section:
            continue
        for m in la["mots"]:
            if m["texte"].lower().strip(",!. ") == mot:
                res.append(m["debut"])
    return tuple(res)


def depuis(t, temps):
    """Temps écoulé depuis le dernier instant de la liste (ou None)."""
    passe = [x for x in temps if x <= t]
    return t - passe[-1] if passe else None


def clignement(t, graine=0):
    rnd = random.Random(graine)
    periode = rnd.uniform(3.0, 4.2)
    return (t + rnd.uniform(0, 3)) % periode < 0.14


# ======================================================================= scènes
def camera_2d(ctx, tl, duree, foyer, occ, zoom0=1.0, zoom1=1.06):
    """Travelling lent vers le foyer ; le sens change selon l'occurrence du plan."""
    u = min(1.0, max(0.0, tl / max(duree, 1e-3)))
    u = u * u * (3 - 2 * u)
    if occ % 2 == 1:
        zoom0, zoom1 = zoom1 + 0.04, zoom0
    z = zoom0 + (zoom1 - zoom0) * u
    fx, fy = foyer
    ctx.translate(fx, fy)
    ctx.scale(z, z)
    ctx.translate(-fx, -fy)


def plan(ctx, nom):
    ctx.set_source_surface(G3["plans"][nom], 0, 0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()


def scene1(ctx, t, tl, duree, occ):
    """Debout dans la salle de bain colorée, timide, il regarde la baignoire pleine de mousse."""
    m = G3["meta"]["timide_a"]
    camera_2d(ctx, tl, duree, (m["tete"][0] + 150, m["tete"][1] + 60), occ, 1.0, 1.08)
    plan(ctx, "large")
    bulles_montantes(ctx, t, (1180, 1560, 460), n=10, graine=4, vitesse=45, r=(10, 30))
    canard(ctx, t, 1470, 455, 190, flip=True)
    if tl < 5.5:
        pose, expr = "timide_a", "timide"
    elif tl < 8.4:
        pose, expr = "timide_b", "timide"
    else:
        pose, expr = "timide_a", "sourire"
    if clignement(t, 1):
        expr = "cligne"
    px, py = G3["meta"][pose]["pieds"]
    ombre(ctx, px, py + 4, 120, 22)
    balance = 0.025 * math.sin(2 * math.pi * t / (4 * C.NOIRE))
    garcon(ctx, pose, expr, rot=balance, sy=1 + 0.008 * math.sin(t * 2.4))


def scene2(ctx, t, tl, duree, occ):
    """Il entre dans le bain en souriant et éclabousse doucement ; bulles colorées."""
    m = G3["meta"]["eclabousse_a"]
    camera_2d(ctx, tl, duree, (m["tete"][0], m["tete"][1] + 120), occ, 1.04, 1.0)
    plan(ctx, "bain")
    bulles_montantes(ctx, t, (380, 1540, 760), n=16, graine=7, vitesse=55, r=(14, 46))
    canard(ctx, t, 600 + 40 * math.sin(t * 0.5), 735, 230)
    b = battue(t)
    pose = "eclabousse_a" if b < 0.4 else ("eclabousse_b" if b < 0.8 else "eclabousse_c")
    expr = "rit" if int(t / (2 * C.NOIRE)) % 2 == 0 else "rit_ferme"
    garcon(ctx, pose, expr, dy=2 * math.sin(t * 3))
    # éclaboussure à chaque battement (mains qui tapent l'eau)
    u = (b - 0.4) * C.NOIRE
    k = int(t / C.NOIRE)
    mb = G3["meta"]["eclabousse_b"]
    for cote, cle in ((-1, "main_g"), (1, "main_d")):
        x, y = mb[cle]
        eclaboussure(ctx, x, y + 10, u, graine=k * 2 + (cote > 0), n=7, force=0.8)


def scene3(ctx, t, tl, duree, occ):
    """Gros plan : il se frotte les mains, puis les montre propres à la caméra, fier."""
    m = G3["meta"]["frotte_a"]
    camera_2d(ctx, tl, duree, (m["tete"][0], m["tete"][1] + 150), occ, 1.0, 1.05)
    plan(ctx, "proche")
    montre = tl > duree * 0.62
    if not montre:
        pose = "frotte_a" if (t / (C.NOIRE / 2)) % 2 < 1 else "frotte_b"
        expr = "cligne" if clignement(t, 3) else "sourire"
        garcon(ctx, pose, expr)
        mx, my = G3["meta"][pose]["main_d"]
        bulles_montantes(ctx, t, (mx - 140, mx + 140, my), n=9, graine=11, vitesse=70, r=(10, 28))
    else:
        u = tl - duree * 0.62
        pop = 1 + 0.06 * math.sin(math.pi * min(1.0, u / 0.35))
        expr = "cligne" if clignement(t, 5) else "rit"
        mm = G3["meta"]["montre"]
        garcon(ctx, "montre", expr, sx=pop, sy=pop, ancre=(mm["tete"][0], H))
        for cle in ("main_g", "main_d"):
            x, y = mm[cle]
            etincelles(ctx, t, x, y - 40, 150, n=7, graine=hash(cle) % 100, alpha=min(1.0, u / 0.3))
    bulles_montantes(ctx, t, (200, 1720, 1000), n=8, graine=12, vitesse=50, r=(16, 40), alpha=0.8)


def reflet_miroir(ctx, pose, expr, cx, cy, rx, ry, zoom, foyer):
    """Reflet du garçon (tête) dans un miroir elliptique : sprite retourné, découpé en ellipse."""
    surf, x0, y0 = G3["garcon"][(pose, expr)]
    fx, fy = foyer
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(rx, ry)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.restore()
    ctx.save()
    ctx.clip()
    ctx.set_source_rgb(*rgb("#d9f3ff"))
    ctx.paint()
    ctx.translate(cx, cy)
    ctx.scale(-zoom, zoom)
    ctx.translate(-fx, -fy)
    ctx.set_source_surface(surf, x0, y0)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint_with_alpha(0.92)
    ctx.restore()
    # voile bleuté + reflet du verre
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(rx, ry)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.set_source_rgba(0.75, 0.9, 1.0, 0.18)
    ctx.fill()
    ctx.restore()
    ctx.save()
    ctx.translate(cx - rx * 0.35, cy - ry * 0.3)
    ctx.rotate(-0.7)
    ctx.scale(rx * 0.12, ry * 0.5)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.set_source_rgba(1, 1, 1, 0.35)
    ctx.fill()
    ctx.restore()


def scene4(ctx, t, tl, duree, occ):
    """Il se lave les cheveux : couronne de mousse, il rigole dans un petit miroir flottant."""
    m = G3["meta"]["cheveux_a"]
    camera_2d(ctx, tl, duree, (m["tete"][0] + 120, m["tete"][1] + 60), occ, 1.0, 1.07)
    plan(ctx, "bain")
    canard(ctx, t, 470 + 30 * math.sin(t * 0.6), 742, 210)
    pose = "cheveux_a" if battue(t) < 0.5 else "cheveux_b"
    expr = "rit" if int(t / (2 * C.NOIRE)) % 2 == 0 else "rit_ferme"
    garcon(ctx, pose, expr, dy=2 * math.sin(t * 3))
    tx, ty = G3["meta"][pose]["tete"]
    bulles_montantes(ctx, t, (tx - 220, tx + 220, ty - 120), n=10, graine=21, vitesse=60, r=(10, 30))
    # miroir flottant à sa gauche (à droite de l'écran), qui le regarde
    mx, my = tx + 420, ty + 20 + 18 * math.sin(t * 1.7)
    larg = 330
    rot = 0.08 * math.sin(t * 1.3)
    ctx.save()
    ctx.translate(mx, my)
    ctx.rotate(rot)
    sprite(ctx, G3["acc"]["miroir"], 0, 0, larg, ancre=(0.5, 0.375))
    r_vitre = larg * 0.5 / 2.0 * 0.95
    reflet_miroir(ctx, pose, expr, 0, 0, r_vitre, r_vitre, 0.62, (tx, ty + 10))
    ctx.restore()
    etincelles(ctx, t, mx, my, 200, n=5, graine=31, alpha=0.8)


def scene5(ctx, t, tl, duree, occ):
    """Il sort du bain dans une serviette à oreilles de canard, tout propre, et saute de joie."""
    m = G3["meta"]["serviette_a"]
    camera_2d(ctx, tl, duree, (m["tete"][0] + 100, m["tete"][1] + 120), occ, 1.0, 1.06)
    plan(ctx, "large")
    bulles_montantes(ctx, t, (1180, 1560, 460), n=8, graine=5, vitesse=45, r=(10, 28))
    canard(ctx, t, 1470, 455, 190, flip=True)
    # un saut toutes les 2 noires : accroupi, envol (bras en l'air), atterrissage
    ph = (t / (2 * C.NOIRE)) % 1.0
    if ph < 0.18:
        pose, h, sq = "serviette_a", 0.0, 1 - 0.07 * math.sin(math.pi * ph / 0.18)
    elif ph < 0.78:
        u = (ph - 0.18) / 0.6
        pose, h, sq = "serviette_b", 150 * math.sin(math.pi * u), 1 + 0.04 * math.sin(math.pi * u)
    else:
        pose, h, sq = "serviette_a", 0.0, 1 - 0.05 * math.sin(math.pi * (ph - 0.78) / 0.22)
    expr = ("rit_ferme" if pose == "serviette_b" else "rit") if not clignement(t, 9) else "cligne"
    px, py = G3["meta"][pose]["pieds"]
    ombre(ctx, px, py + 4, 120 * (1 - h / 400), 22 * (1 - h / 400))
    garcon(ctx, pose, expr, dy=-h, sx=2 - sq, sy=sq)
    tx, ty = G3["meta"][pose]["tete"]
    etincelles(ctx, t, tx, ty - h, 300, n=9, graine=41)


def positions_bulles_compte():
    res = []
    for k in (1, 2, 3):
        m = G3["meta"][f"compte_{k}"]
        hx, hy = m["main_g" if k == 1 else "main_d"]
        tx, ty = m["tete"]
        dx, dy = hx - tx, hy - ty
        n = math.hypot(dx, dy) or 1
        res.append((hx + dx / n * 170, hy + dy / n * 170 - 30))
    return res


def scene6(ctx, t, tl, duree, occ):
    """Dans le bain, il compte les bulles en pointant du doigt : un, deux, trois."""
    m = G3["meta"]["compte_2"]
    camera_2d(ctx, tl, duree, (m["tete"][0], m["tete"][1] - 40), occ, 1.0, 1.05)
    plan(ctx, "bain")
    canard(ctx, t, 520, 745, 220)
    bulles_montantes(ctx, t, (300, 1600, 800), n=8, graine=61, vitesse=35, r=(12, 30), alpha=0.7)
    pos = positions_bulles_compte()
    if occ == 0:
        # sur les paroles : « un, deux, trois » → la bulle correspondante s'allume
        moments = [instants(w, "couplet 3")[0] for w in ("un", "deux", "trois")]
    else:
        # deuxième plan : on recompte doucement, une bulle par noire, toutes les 2 mesures
        base = math.floor(t / (2 * C.MESURE)) * 2 * C.MESURE
        moments = [base + k * 2 * C.NOIRE for k in range(3)]
    actif = 0
    for k, mt in enumerate(moments):
        if t >= mt - 0.05:
            actif = k + 1
    if actif == 0:
        pose, expr = "compte_2", "concentre"
    else:
        pose = f"compte_{actif}"
        expr = "concentre" if t - moments[actif - 1] < 0.9 * C.NOIRE else "rit"
    if occ == 1 and actif == 0:
        pose, expr = "compte_3", "rit"
    garcon(ctx, pose, expr, dy=2 * math.sin(t * 2.5))
    for k, (x, y) in enumerate(pos):
        flotte = 10 * math.sin(t * 1.4 + k * 2)
        allume = t >= moments[k] - 0.05
        u = t - moments[k]
        grossit = 1 + (0.25 * math.sin(math.pi * min(1.0, u / 0.35)) if 0 <= u < 0.35 else 0)
        r = 78 * grossit
        bulle(ctx, x, y + flotte, r, 1.0, teinte=k)
        if allume:
            # le chiffre est écrit plus tard, avec le texte (voir dessiner_textes)
            ux, uy = ctx.user_to_device(x, y + flotte)
            e = R.G["echelle"]
            G3["chiffres"].append((ux / e, uy / e, k, grossit))
            etincelles(ctx, t, x, y + flotte, 120, n=4, graine=k + 70, alpha=min(1.0, max(0.0, u) / 0.2))


def scene7(ctx, t, tl, duree, occ):
    """En pyjama propre, il se brosse les dents devant un miroir rigolo."""
    m = G3["meta"]["brosse_a"]
    camera_2d(ctx, tl, duree, (m["tete"][0] + 250, m["tete"][1] + 80), occ, 1.0, 1.07)
    plan(ctx, "lavabo")
    pose_r = "brosse_a" if (t / (C.NOIRE / 2)) % 2 < 1 else "brosse_b"
    fin_dents = tl > duree * 0.55          # après le brossage : sourire au miroir
    if fin_dents:
        pose_r = "brosse_a"
    expr = "brosse_cligne" if clignement(t, 13) else "brosse"
    px, py = G3["meta"][pose_r]["pieds"]
    garcon(ctx, pose_r, expr, sy=1 + 0.006 * math.sin(t * 2.2))
    # reflet dans le miroir rigolo
    v = G3["plans_meta"]["lavabo"]["vitre"]
    xs, ys = [p[0] for p in v], [p[1] for p in v]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    rx, ry = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
    reflet = "reflet_a" if pose_r == "brosse_a" else "reflet_b"
    mr = G3["meta"][reflet]
    reflet_miroir(ctx, reflet, "brosse", cx, cy + ry * 0.12, rx, ry, 0.95, (mr["tete"][0], mr["tete"][1] + 60))
    bulles_montantes(ctx, t, (cx - 300, cx + 300, 1000), n=6, graine=81, vitesse=40, r=(10, 26), alpha=0.7)


SCENES = {1: scene1, 2: scene2, 3: scene3, 4: scene4, 5: scene5, 6: scene6, 7: scene7}


# ======================================================================= montage
def plan_index(t):
    plans = G3["plans_montage"]
    idx = 0
    for k, p in enumerate(plans):
        if t >= p[0] - 1e-9:
            idx = k
    return idx


def dessiner_plan(ctx, idx, t):
    debut, fin, sc, _k, occ = G3["plans_montage"][idx]
    ctx.save()
    SCENES[sc](ctx, t, t - debut, fin - debut, occ)
    ctx.restore()


def dessiner_monde(ctx, t):
    idx = plan_index(t)
    debut = G3["plans_montage"][idx][0]
    G3["chiffres"] = []
    if idx > 0 and t - debut < TRANSITION:
        u = (t - debut) / TRANSITION
        u = u * u * (3 - 2 * u)
        dessiner_plan(ctx, idx - 1, t)
        G3["chiffres"] = []
        r = u * math.hypot(W / 2, H / 2) * 1.05
        ctx.save()
        ctx.arc(W / 2, H / 2, max(r, 0.1), 0, 2 * math.pi)
        ctx.clip()
        dessiner_plan(ctx, idx, t)
        ctx.restore()
        ctx.set_source_rgba(1, 1, 1, 0.9)
        ctx.set_line_width(26 * (1 - u) + 4)
        ctx.arc(W / 2, H / 2, max(r, 0.1), 0, 2 * math.pi)
        ctx.stroke()
        # quelques bulles sur le bord de la transition
        for k in range(10):
            a = k / 10 * 2 * math.pi + t
            bulle(ctx, W / 2 + r * math.cos(a), H / 2 + r * math.sin(a), 30 + 10 * (k % 3), 1 - u, teinte=k)
    else:
        dessiner_plan(ctx, idx, t)


# ======================================================================= textes
TEXTE_DODO = "Propre et prêt pour dodo !"


def titre_rebondissant(draw, t, texte, y, taille, apparition, disparition):
    taille = taille * apparition * disparition
    if taille <= 4:
        return
    lettres = list(texte)
    larg = [R.largeur(c, taille) for c in lettres]
    total = sum(larg)
    if total > W - 120:
        k = (W - 120) / total
        taille *= k
        larg = [w * k for w in larg]
        total = sum(larg)
    x = (W - total) / 2
    for k, (c, wl) in enumerate(zip(lettres, larg)):
        if c != " ":
            ph = (t / C.NOIRE - k * 0.12) % 1
            dy = -24 * abs(math.sin(math.pi * ph))
            R.texte_contour(draw, (x + wl / 2, y + dy), c, taille, C.PALETTE[k % len(C.PALETTE)], ep=14)
        x += wl


def dessiner_textes(draw, t):
    # titre pendant l'intro instrumentale
    if t < 5.2:
        a = min(1.0, t / 0.6)
        d = min(1.0, max(0.0, (5.2 - t) / 0.5))
        titre_rebondissant(draw, t, B.TITRE, 300, 140, a, d)
    # chiffres dans les bulles (scène 6)
    for x, y, k, g in G3.get("chiffres", []):
        R.texte_contour(draw, (x, y + 40), str(k + 1), 120 * g, C.PALETTE[(k * 2) % 7], ep=13)
    # texte de la scène 7
    debut7 = next(p[0] for p in G3["plans_montage"] if p[2] == 7)
    if t > debut7 + 1.5:
        a = min(1.0, (t - debut7 - 1.5) / 0.5)
        titre_rebondissant(draw, t, TEXTE_DODO, 190, 112, a, 1.0)


# ======================================================================= image
def rendre_image(t):
    e = R.G["echelle"]
    w, h = int(W * e), int(H * e)
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    ctx = cairo.Context(surf)
    ctx.scale(e, e)
    dessiner_monde(ctx, t)
    # éclaboussures sur chaque « splash » (gerbe depuis le bas de l'image)
    for k, ti in enumerate(instants("splash")):
        u = t - ti
        if 0 <= u < 0.9:
            eclaboussure(ctx, [380, 960, 1540][k % 3], H + 30, u, graine=500 + k, n=14, force=1.3)
    # fondu de fin (dernière seconde) vers un bleu nuit doux
    if t > C.DUREE_TOTALE - 1.2:
        u = (t - (C.DUREE_TOTALE - 1.2)) / 1.2
        ctx.set_source_rgba(0.16, 0.15, 0.4, min(1.0, u) * 0.85)
        ctx.paint()
    surf.flush()
    a = np.ndarray((h, surf.get_stride() // 4, 4), np.uint8, surf.get_data())[:, :w, 2::-1]
    img = Image.fromarray(np.ascontiguousarray(a), "RGB")
    draw = ImageDraw.Draw(img)
    dessiner_textes(draw, t)
    R.dessiner_karaoke(draw, t)
    return img


def rendre_video(lignes, audio, sortie, dossier_tmp, echelle=1.0, processus=None, debut=0.0, fin=None):
    R.rendre_video(lignes, audio, sortie, dossier_tmp, echelle, processus, debut, fin,
                   init=init_worker, image=rendre_image)


def apercu(lignes, temps, chemin, echelle=0.5):
    init_worker(preparer_donnees(lignes), echelle)
    rendre_image(temps).save(chemin)

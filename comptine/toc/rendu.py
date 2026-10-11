"""Animation 2D de « Toc toc toc, qui est là ? » (cairo, 1920x1080, 30 i/s).

Ordre des plans : ciel → fond → (personnages cachés) → milieu → personnages →
devant → effets (pluie, feu, étoiles, confettis, bulles « TOC ! ») → titres → karaoké.
Les décors SVG sont en couches, avec une parallaxe lente.
Chaque personnage est un rig de pièces SVG (voir svg.py) : rebond en rythme,
balancement de la tête, des oreilles, des bras et de la queue, clignement des
yeux, bouche ouverte sur les syllabes qu'il chante.
"""
import json
import math
import random

import cairo
import numpy as np
from PIL import Image, ImageDraw

from .. import config as C
from .. import rendu as R
from . import chanson as T
from .actifs import DOSSIER

W, H = C.LARGEUR, C.HAUTEUR
LW = 2100
SOL = 950
PIEDS = 900          # pieds des personnages en intérieur : le karaoké (en bas) ne les cache pas
TRANSITION = 0.5
G = {}


# ======================================================================= chargement
def surf(nom):
    return cairo.ImageSurface.create_from_png(str(DOSSIER / "png" / f"{nom}.png"))


def charger():
    if "rig" in G:
        return
    G["rig"] = json.loads((DOSSIER / "png" / "rig.json").read_text())
    G["pieces"] = {(p, k): surf(f"{p}_{k}") for p, pieces in G["rig"].items() for k in pieces}
    G["acc"] = {n: surf(n) for n in ("gateau", "parapluie_jaune", "parapluie_rose", "oiseau_a", "oiseau_b")}
    G["decors"] = {}
    for f in (DOSSIER / "png").glob("decor_*.png"):
        _, nom_couche = f.stem.split("_", 1)
        nom, couche = nom_couche.rsplit("_", 1)
        G["decors"][(nom, couche)] = cairo.ImageSurface.create_from_png(str(f))


def preparer_donnees(lignes):
    d = R.preparer_donnees(lignes)
    chants = []           # (début, fin, personnage) de chaque syllabe
    for L in lignes:
        qui = T.voix_des_mots(L)
        for s in L.syllabes:
            chants.append((s.debut, s.fin, qui[s.mot][1]))
    d["chants"] = sorted(chants)
    d["toc"] = [m["debut"] for m in d["mots"] if m["texte"].lower().strip(",!.…? ") == "toc"]
    return d


def init_worker(donnees, echelle):
    R.G["d"] = donnees
    R.G["echelle"] = echelle
    charger()
    G["plans"] = donnees["plans"]
    G["phase"] = donnees.get("phase", 0.0)
    G["chants"] = donnees["chants"]
    G["toc"] = donnees["toc"]
    G["lignes"] = donnees["lignes"]


# ======================================================================= outils
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def tm(t):
    return t - G.get("phase", 0.0)


def battement(t, div=1.0):
    """Phase (0..1) dans le battement (div = 2 : deux fois plus lent)."""
    return (tm(t) / (C.NOIRE * div)) % 1.0


def chante(perso, t, tous=()):
    for d, f, p in G["chants"]:
        if d - 0.03 <= t < d + max(0.12, 0.8 * (f - d)):
            if p == perso or (p == "tous" and perso in tous):
                return True
        if d > t + 0.1:
            break
    return False


def clin(nom, t):
    rnd = random.Random(sum(map(ord, nom)))
    per = rnd.uniform(2.8, 4.0)
    return (t + rnd.uniform(0, 3)) % per < 0.13


def peindre(ctx, s, x, y, alpha=1.0):
    ctx.set_source_surface(s, x, y)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    if alpha >= 1:
        ctx.paint()
    else:
        ctx.paint_with_alpha(alpha)


def tourner(ctx, px, py, a, sx=1.0, sy=1.0):
    ctx.translate(px, py)
    ctx.rotate(a)
    ctx.scale(sx, sy)
    ctx.translate(-px, -py)


# ======================================================================= personnages
def personnage(ctx, nom, x, y, echelle, t, rebond=18.0, danse=0.0, flip=False, chant=None, yeux=None,
               bras=None, tete=0.0, alpha=1.0, phase=0.0, accessoire=None):
    """Dessine le personnage `nom`, pieds en (x, y), haut d'environ 720·échelle px.

    rebond : amplitude du rebond (px) sur le temps ; danse : 0..1, bras levés qui balancent ;
    chant : bouche ouverte ; yeux : « ouverts », « fermes » ou None (clignements) ;
    bras : (angle gauche, angle droit) en degrés imposés ; tete : inclinaison (rad)."""
    rig = G["rig"][nom]
    b = (battement(t) + phase) % 1.0
    saut = abs(math.sin(math.pi * b))
    dy = -rebond * saut
    ecrase = 1 - 0.05 * math.exp(-b * 10) * (1 if rebond > 2 else 0)
    oscil = math.sin(2 * math.pi * (tm(t) / (2 * C.NOIRE) + phase))
    a_corps = 0.035 * oscil * (0.4 + danse)
    a_tete = tete + 0.07 * math.sin(2 * math.pi * (tm(t) / (2 * C.NOIRE) + phase + 0.2))
    if bras is None:
        lev = danse * (100 + 30 * oscil)
        bras = (lev + 12 * oscil, -lev + 12 * oscil)
    a_bras = {"bras_g": math.radians(bras[0]), "bras_d": math.radians(bras[1])}
    a_oreille = {"oreille_g": 0.12 * math.sin(2 * math.pi * (tm(t) / (2 * C.NOIRE) + phase + 0.45)),
                 "oreille_d": -0.12 * math.sin(2 * math.pi * (tm(t) / (2 * C.NOIRE) + phase + 0.6))}
    a_queue = 0.3 * math.sin(tm(t) * 2 * math.pi / C.NOIRE)
    if yeux is None:
        yeux = "fermes" if clin(nom, t) else "ouverts"
    cache = {"yeux_fermes" if yeux == "ouverts" else "yeux_ouverts", "bouche_fermee" if chant else "bouche_ouverte"}

    ctx.save()
    ctx.translate(x, y + dy)
    ctx.scale(echelle * (-1 if flip else 1), echelle)
    ctx.translate(-300, -690)
    for piece, info in sorted(rig.items(), key=lambda kv: kv[1]["z"]):
        if piece in cache:
            continue
        s = G["pieces"][(nom, piece)]
        ctx.save()
        # corps : balancement + écrasement autour des pieds
        tourner(ctx, 300, 690, a_corps, 2 - ecrase, ecrase)
        px, py = info["pivot"]
        if info["parent"] == "tete" or piece == "tete":
            tp = rig["tete"]["pivot"]
            tourner(ctx, tp[0], tp[1], a_tete)
        if piece in a_bras:
            tourner(ctx, px, py, a_bras[piece])
        elif piece in a_oreille:
            tourner(ctx, px, py, a_oreille[piece])
        elif piece == "queue":
            tourner(ctx, px, py, a_queue)
        peindre(ctx, s, *info["decalage"], alpha)
        ctx.restore()
    if accessoire:
        nom_acc, ax, ay, larg = accessoire
        sa = G["acc"][nom_acc]
        k = larg / sa.get_width()
        ctx.save()
        tourner(ctx, 300, 690, a_corps, 2 - ecrase, ecrase)
        ctx.translate(ax, ay)
        ctx.rotate(0.05 * oscil)
        ctx.scale(k, k)
        ctx.translate(-sa.get_width() / 2, -sa.get_height())
        peindre(ctx, sa, 0, 0, alpha)
        ctx.restore()
    ctx.restore()
    # ombre au sol (sous le personnage, ne suit pas le saut)
    return dy


def ombre(ctx, x, y, rx, ry=None, alpha=0.22):
    ry = ry or rx * 0.18
    g = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
    g.add_color_stop_rgba(0, 0.2, 0.1, 0.25, alpha)
    g.add_color_stop_rgba(1, 0.2, 0.1, 0.25, 0)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(rx, ry)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.set_source(g)
    ctx.fill()
    ctx.restore()


def perso_au_sol(ctx, nom, x, y, echelle, t, **k):
    ombre(ctx, x, y + 4, 150 * echelle)
    return personnage(ctx, nom, x, y, echelle, t, **k)


# ======================================================================= effets
def pluie(ctx, t, zone=(0, 0, W, H), n=140, graine=1, vitesse=1300, alpha=0.55):
    x0, y0, w, h = zone
    rnd = random.Random(graine)
    ctx.save()
    ctx.rectangle(x0, y0, w, h)
    ctx.clip()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for _ in range(n):
        x = rnd.uniform(x0, x0 + w + 200)
        ph = rnd.uniform(0, h + 60)
        v = vitesse * rnd.uniform(0.8, 1.2)
        y = y0 + (ph + t * v) % (h + 60) - 30
        xx = x - (y - y0) * 0.18
        l = rnd.uniform(16, 30)
        ctx.set_line_width(rnd.uniform(2.5, 4))
        ctx.set_source_rgba(0.85, 0.92, 1.0, alpha)
        ctx.move_to(xx, y)
        ctx.line_to(xx - l * 0.18, y + l)
        ctx.stroke()
    ctx.restore()


def flaques(ctx, t, positions):
    for k, (x, y) in enumerate(positions):
        u = (t * 1.3 + k * 0.37) % 1
        ctx.set_source_rgba(1, 1, 1, 0.6 * (1 - u))
        ctx.set_line_width(3)
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(1, 0.25)
        ctx.arc(0, 0, 10 + 50 * u, 0, 2 * math.pi)
        ctx.restore()
        ctx.stroke()


def feu(ctx, t, x, y, s=1.0):
    """Petites flammes de cheminée qui dansent."""
    for k, (dx, h, c) in enumerate(((-40, 90, "#ff6b2b"), (35, 80, "#ff6b2b"), (0, 120, "#ffa62b"),
                                    (-15, 70, "#ffd23f"), (20, 65, "#ffd23f"))):
        hh = h * s * (0.85 + 0.15 * math.sin(t * 9 + k * 1.7))
        ww = 34 * s
        xx = x + dx * s + 4 * math.sin(t * 7 + k)
        ctx.move_to(xx - ww, y)
        ctx.curve_to(xx - ww, y - hh * 0.5, xx - 5, y - hh * 0.6, xx, y - hh)
        ctx.curve_to(xx + 5, y - hh * 0.6, xx + ww, y - hh * 0.5, xx + ww, y)
        ctx.close_path()
        ctx.set_source_rgb(*rgb(c))
        ctx.fill()
    g = cairo.RadialGradient(x, y - 50 * s, 10, x, y - 50 * s, 320 * s)
    g.add_color_stop_rgba(0, 1, 0.75, 0.3, 0.25 + 0.05 * math.sin(t * 6))
    g.add_color_stop_rgba(1, 1, 0.75, 0.3, 0)
    ctx.set_source(g)
    ctx.arc(x, y - 50 * s, 320 * s, 0, 2 * math.pi)
    ctx.fill()


def etoiles(ctx, t, n=40, graine=4, y_max=500, alpha=1.0):
    rnd = random.Random(graine)
    for k in range(n):
        x, y = rnd.uniform(0, W), rnd.uniform(0, y_max)
        sc = 0.5 + 0.5 * math.sin(t * rnd.uniform(1.5, 3.5) + rnd.uniform(0, 6))
        r = rnd.uniform(6, 13) * (0.6 + 0.4 * sc)
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(0.3 * math.sin(t + k))
        ctx.move_to(0, -r)
        for i in range(1, 10):
            a = i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            ctx.line_to(rr * math.sin(a), -rr * math.cos(a))
        ctx.close_path()
        ctx.set_source_rgba(1, 0.95, 0.6, alpha * (0.5 + 0.5 * sc))
        ctx.fill()
        ctx.restore()


def confettis(ctx, t, n=80, graine=11, intensite=1.0):
    rnd = random.Random(graine)
    cols = [rgb(c) for c in ("#ff5252", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#ab47bc", "#ff80ab")]
    for k in range(int(n * intensite)):
        x0 = rnd.uniform(0, W)
        v = rnd.uniform(90, 200)
        ph = rnd.uniform(0, H + 100)
        y = (ph + t * v) % (H + 100) - 50
        x = x0 + 40 * math.sin(t * rnd.uniform(1, 2.5) + k)
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(t * rnd.uniform(-4, 4))
        ctx.scale(1, abs(math.sin(t * rnd.uniform(2, 5) + k)) + 0.2)
        ctx.rectangle(-8, -5, 16, 10)
        ctx.set_source_rgb(*cols[k % 7])
        ctx.fill()
        ctx.restore()


def ballons(ctx, t, n=7, graine=5):
    rnd = random.Random(graine)
    cols = [rgb(c) for c in ("#ff5252", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#ab47bc", "#ff80ab")]
    for k in range(n):
        x0 = rnd.uniform(60, W - 60)
        v = rnd.uniform(40, 70)
        ph = rnd.uniform(0, H + 400)
        y = H + 200 - (ph + t * v) % (H + 400)
        x = x0 + 30 * math.sin(t * 1.1 + k)
        ctx.set_source_rgba(0.3, 0.2, 0.35, 0.8)
        ctx.set_line_width(3)
        ctx.move_to(x, y + 75)
        ctx.curve_to(x + 15, y + 120, x - 15, y + 160, x, y + 210)
        ctx.stroke()
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(1, 1.18)
        ctx.arc(0, 0, 62, 0, 2 * math.pi)
        ctx.restore()
        ctx.set_source_rgb(*cols[k % 7])
        ctx.fill_preserve()
        ctx.set_source_rgb(*rgb("#3a2340"))
        ctx.set_line_width(5)
        ctx.stroke()
        ctx.arc(x - 20, y - 28, 14, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 0.55)
        ctx.fill()


def notes(ctx, t, n=7, graine=13):
    rnd = random.Random(graine)
    cols = ["#ff5252", "#42a5f5", "#ab47bc", "#ffa726", "#66bb6a"]
    for k in range(n):
        x0 = rnd.uniform(150, W - 150)
        ph = (t * 0.25 + k / n) % 1
        x, y = x0 + 40 * math.sin(ph * 12 + k), 760 - ph * 620
        a = math.sin(ph * math.pi)
        ctx.set_source_rgba(*rgb(cols[k % 5]), a)
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(1, 0.8)
        ctx.arc(0, 0, 16, 0, 2 * math.pi)
        ctx.restore()
        ctx.fill()
        ctx.rectangle(x + 12, y - 58, 6, 58)
        ctx.fill()


def bulle_toc(ctx, x, y, u, texte="TOC !", couleur="#ffd23f"):
    """Bulle « TOC ! » en étoile qui jaillit (u = temps depuis le coup, s)."""
    if not 0 <= u < 0.55:
        return
    pop = math.sin(math.pi * min(1.0, u / 0.25)) * 0.25 + min(1.0, u / 0.12)
    a = 1 - max(0.0, (u - 0.35) / 0.2)
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(pop, pop)
    ctx.rotate(-0.12)
    ctx.move_to(0, -95)
    for i in range(1, 24):
        ang = i * math.pi / 12
        r = 95 if i % 2 == 0 else 65
        ctx.line_to(r * 1.5 * math.sin(ang), -r * math.cos(ang))
    ctx.close_path()
    ctx.set_source_rgba(*rgb(couleur), a)
    ctx.fill_preserve()
    ctx.set_source_rgba(*rgb("#3a2340"), a)
    ctx.set_line_width(6)
    ctx.stroke()
    ctx.select_font_face("Fredoka", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(54)
    ext = ctx.text_extents(texte)
    ctx.move_to(-ext.width / 2 - ext.x_bearing, ext.height / 2)
    ctx.text_path(texte)
    ctx.set_source_rgba(1, 1, 1, a)
    ctx.set_line_width(10)
    ctx.stroke_preserve()
    ctx.set_source_rgba(*rgb("#ef4b5f"), a)
    ctx.fill()
    ctx.restore()


def tocs(ctx, t, positions):
    """Une bulle « TOC ! » sur chaque « toc » chanté, en alternant les positions."""
    for k, ti in enumerate(G["toc"]):
        u = t - ti
        if 0 <= u < 0.55:
            x, y = positions[k % len(positions)]
            bulle_toc(ctx, x, y, u)


def point_interrogation(ctx, x, y, t, a=1.0):
    ctx.save()
    ctx.translate(x, y + 8 * math.sin(t * 5))
    ctx.rotate(0.15 * math.sin(t * 3))
    ctx.select_font_face("Fredoka", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(140)
    ctx.move_to(-35, 50)
    ctx.text_path("?")
    ctx.set_source_rgba(1, 1, 1, a)
    ctx.set_line_width(14)
    ctx.stroke_preserve()
    ctx.set_source_rgba(*rgb("#ab47bc"), a)
    ctx.fill()
    ctx.restore()


# ======================================================================= décors
def couche(ctx, decor, nom, dx, alpha=1.0):
    s = G["decors"].get((decor, nom))
    if s:
        peindre(ctx, s, dx, 0, alpha)


def decalages(u):
    """Décalage x de chaque couche (parallaxe lente pendant le plan)."""
    base = -(LW - W) / 2
    v = (u - 0.5) * 2              # -1 → 1
    return {"ciel": base - 15 * v, "fond": base - 40 * v, "milieu": base - 75 * v, "devant": base - 110 * v}


def zoom(ctx, u, fx=W / 2, fy=H * 0.75, z0=1.0, z1=1.04):
    z = z0 + (z1 - z0) * (u * u * (3 - 2 * u))
    ctx.translate(fx, fy)
    ctx.scale(z, z)
    ctx.translate(-fx, -fy)


# ======================================================================= scènes
def lignes_de(section):
    return [la for la in G["lignes"] if la["section"] == section]


def debut_ligne(texte, section, apres=0.0):
    for la in G["lignes"]:
        if la["section"] == section and la["texte"].startswith(texte) and la["debut"] >= apres - 1e-6:
            return la["debut"]
    return None


def scene(ctx, t, plan):
    debut, fin, decor, section, n_final = plan
    tl = t - debut
    duree = max(fin - debut, 1e-3)
    u = min(1.0, max(0.0, tl / duree))
    dx = decalages(u)
    ctx.save()
    zoom(ctx, u)
    couche(ctx, decor, "ciel", dx["ciel"])
    m = dx["milieu"]             # repère des personnages : coordonnées du décor (2100 de large)

    if decor in ("colline", "colline_nuit"):
        nuit = decor == "colline_nuit"
        if nuit:
            etoiles(ctx, t, 40, 4, 520)
        couche(ctx, decor, "fond", dx["fond"])
        couche(ctx, decor, "milieu", m)
        if not nuit:
            # Cochon et Biquette arrivent sous leurs parapluies vers la maison
            av = min(1.0, tl / 10.0)
            perso_au_sol(ctx, "cochon", 300 + 420 * av + m, 905, 0.38, t, rebond=10, phase=0.0,
                         accessoire=("parapluie_jaune", 380, 330, 520))
            perso_au_sol(ctx, "biquette", 120 + 420 * av + m, 915, 0.38, t, rebond=10, phase=0.5,
                         accessoire=("parapluie_rose", 220, 330, 520))
            tocs(ctx, t, [(1060 + m, 560), (1180 + m, 470), (940 + m, 470)])
        else:
            for k, nom in enumerate(("lapin", "cochon", "biquette", "hibou", "croco")):
                x = 640 + k * 205 + m
                perso_au_sol(ctx, nom, x, 925, 0.33, t, rebond=8, phase=0.15 * k,
                             bras=(25 + 60 * max(0, math.sin(t * 5 + k)), -25 - 60 * max(0, math.sin(t * 5 + k))),
                             chant=chante(nom, t, T_TOUS), yeux=None)
        couche(ctx, decor, "devant", dx["devant"])
        if not nuit:
            pluie(ctx, t, n=160)

    elif decor == "cuisine":
        couche(ctx, decor, "fond", dx["fond"])
        pluie(ctx, t, (1300 + dx["fond"], 180, 420, 360), n=25, alpha=0.7)
        couche(ctx, decor, "milieu", m)
        t_mais = debut_ligne("Mais tout à coup", section, debut) or 1e9
        surpris = t >= t_mais - 0.1
        x_lapin = 820 + m
        perso_au_sol(ctx, "lapin", x_lapin, PIEDS - 30, 0.6, t, rebond=0 if surpris else 10,
                     bras=None if surpris else (40 + 25 * math.sin(t * 6), -15),
                     chant=chante("lapin", t), flip=surpris, tete=0.08 * math.sin(t * 2))
        if surpris:
            point_interrogation(ctx, x_lapin + 150, 380, t, min(1.0, (t - t_mais) / 0.3))
            tocs(ctx, t, [(1510 + dx["fond"], 330), (1610 + dx["fond"], 260)])
            t_quel = debut_ligne("Quelqu'un frappe", section, debut) or 1e9
            for k in range(3):
                bulle_toc(ctx, 1450 + 110 * k + dx["fond"], 300 + 40 * (k % 2), t - t_quel - 0.45 * k)
        couche(ctx, decor, "devant", dx["devant"])

    elif decor in ("salon", "fete"):
        fete = decor == "fete"
        couche(ctx, decor, "fond", dx["fond"])
        feu(ctx, t, 1500 + dx["fond"], SOL - 135, 1.0)
        couche(ctx, decor, "milieu", m)
        if fete:
            ballons(ctx, t)
            sa = G["acc"]["gateau"]
            k = 300 / sa.get_width()
            ctx.save()
            ctx.translate(1040 + m - 150, SOL - 190 - sa.get_height() * k)
            ctx.scale(k, k)
            peindre(ctx, sa, 0, 0)
            ctx.restore()
        if fete:
            noms = ["biquette", "hibou", "lapin", "croco", "cochon"]
            xs = [330, 640, 960, 1330, 1680]
            ech = [0.5, 0.5, 0.6, 0.6, 0.5]
            dan = 1.0 if n_final >= 2 else 0.7
        else:
            # Biquette rejoint les refrains après s'être présentée au couplet 2
            avec_biquette = any(p[2] == "porte" and p[0] < debut for p in G["plans"])
            noms = ["lapin", "cochon"] + (["biquette"] if avec_biquette else [])
            xs = [760, 1300, 1650] if avec_biquette else [800, 1300]
            ech = [0.62, 0.62, 0.52]
            dan = 0.6
        tous = set(noms)
        for k, (nom, x, e) in enumerate(zip(noms, xs, ech)):
            perso_au_sol(ctx, nom, x + m, PIEDS, e, t, rebond=22 if fete else 16, danse=dan, phase=0.5 * (k % 2),
                         chant=chante(nom, t, tous))
        couche(ctx, decor, "devant", dx["devant"])
        if fete:
            confettis(ctx, t, intensite=1.4 if n_final >= 2 else 1.0)
        else:
            notes(ctx, t)
            tocs(ctx, t, [(380, 260), (1540, 240), (960, 200)])

    elif decor == "porte":
        couche(ctx, decor, "fond", dx["fond"])
        # le lapin dans l'encadrement de la porte (derrière la façade)
        perso_au_sol(ctx, "lapin", 1050 + m, SOL - 55, 0.6, t, rebond=6, chant=chante("lapin", t),
                     bras=(30, -30 - 40 * chante("lapin", t)))
        couche(ctx, decor, "milieu", m)
        t_biq = debut_ligne("Et puis là", section, debut) or 1e9
        perso_au_sol(ctx, "cochon", 560 + m, PIEDS, 0.58, t, rebond=12, chant=chante("cochon", t),
                     accessoire=("parapluie_jaune", 400, 300, 560))
        if t >= t_biq - 0.6:
            arr = min(1.0, (t - t_biq + 0.6) / 0.8)
            perso_au_sol(ctx, "biquette", 1500 + 400 * (1 - arr) + m, PIEDS, 0.58, t, rebond=12, phase=0.5,
                         chant=chante("biquette", t), accessoire=("parapluie_rose", 220, 300, 560))
        couche(ctx, decor, "devant", dx["devant"])
        flaques(ctx, t, [(400 + dx["devant"], 1030), (1650 + dx["devant"], 1050)])
        pluie(ctx, t, n=170)

    elif decor == "fenetre":
        couche(ctx, decor, "fond", dx["fond"])
        f = dx["fond"]
        pluie(ctx, t, (700 + f, 160, 700, 520), n=40, alpha=0.6)
        t_hou = debut_ligne("Hou hou", section, debut) or 1e9
        if t >= t_hou - 0.8:
            arr = min(1.0, (t - t_hou + 0.8) / 0.8)
            personnage(ctx, "hibou", 1050 + f, 690 - 250 * (1 - arr), 0.4, t, rebond=4, chant=chante("hibou", t),
                       bras=(60 * max(0, math.sin(t * 8)), -60 * max(0, math.sin(t * 8))))
        couche(ctx, decor, "milieu", m)
        feu(ctx, t, 330 + m, SOL - 135, 1.0)
        dodo = t < t_hou - 0.3
        for k, (nom, x) in enumerate((("biquette", 1480), ("cochon", 1760), ("lapin", 1120))):
            perso_au_sol(ctx, nom, x + m, PIEDS, 0.52, t, rebond=3, yeux="fermes" if dodo and nom != "lapin" else None,
                         chant=chante(nom, t), phase=0.3 * k, tete=0.12 if dodo and nom != "lapin" else 0.0)
        couche(ctx, decor, "devant", dx["devant"])

    elif decor == "porte_nuit":
        couche(ctx, decor, "fond", dx["fond"])
        t_yeux = debut_ligne("Deux gros yeux", section, debut) or 1e9
        t_croco = debut_ligne("C'est Croco", section, debut) or 1e9
        x_porte = 1050 + m
        if t_yeux - 0.2 <= t < t_croco:
            # deux gros yeux et un sourire qui brillent dans le noir (rigolo, pas effrayant)
            a = min(1.0, (t - t_yeux + 0.2) / 0.5)
            cl = clin("croco", t)
            for s_ in (-1, 1):
                ctx.save()
                ctx.translate(x_porte + s_ * 55, 600)
                ctx.scale(1, 0.15 if cl else 1)
                ctx.arc(0, 0, 38, 0, 2 * math.pi)
                ctx.restore()
                ctx.set_source_rgba(1, 1, 0.75, a)
                ctx.fill()
                ctx.arc(x_porte + s_ * 55 + 6, 606, 16, 0, 2 * math.pi)
                ctx.set_source_rgba(0.1, 0.05, 0.15, a if not cl else 0)
                ctx.fill()
            for k in range(-3, 4):
                xx = x_porte + k * 26
                ctx.move_to(xx - 12, 690)
                ctx.line_to(xx + 12, 690)
                ctx.line_to(xx, 712)
                ctx.close_path()
                ctx.set_source_rgba(1, 1, 1, a)
                ctx.fill()
        if t >= t_croco - 0.3:
            arr = min(1.0, (t - t_croco + 0.3) / 0.6)
            perso_au_sol(ctx, "croco", x_porte, PIEDS - 20 + 80 * (1 - arr), 0.62, t, rebond=12, chant=chante("croco", t),
                         bras=(-70, 70), accessoire=None)
            sa = G["acc"]["gateau"]
            k = 260 / sa.get_width()
            ctx.save()
            ctx.translate(x_porte - 130, 640 + 80 * (1 - arr) - 10 * abs(math.sin(math.pi * battement(t))))
            ctx.scale(k, k)
            peindre(ctx, sa, 0, 0)
            ctx.restore()
        # les amis cachés derrière le fauteuil (ils tremblent pour rire, puis se relèvent)
        rel = 0.0 if t < t_croco else min(1.0, (t - t_croco - 0.3) / 0.6)
        for k, (nom, x) in enumerate((("hibou", 230), ("cochon", 380), ("lapin", 530))):
            trem = 4 * math.sin(t * 40 + k) * (1 - rel)
            personnage(ctx, nom, x + m + trem, SOL - 70 - 110 * rel, 0.5, t, rebond=2 + 10 * rel,
                       chant=chante(nom, t), yeux="ouverts" if not clin(nom, t) else "fermes")
        couche(ctx, decor, "milieu", m)
        perso_au_sol(ctx, "biquette", 1650 + m, PIEDS, 0.52, t, rebond=3 + 9 * rel, chant=chante("biquette", t),
                     bras=(-20, 20) if rel == 0 else None, danse=0.5 * rel)
        tocs(ctx, t, [(x_porte - 160, 400), (x_porte + 160, 360), (x_porte, 300)])
        couche(ctx, decor, "devant", dx["devant"])
    ctx.restore()


T_TOUS = {"lapin", "cochon", "biquette", "hibou", "croco"}


# ======================================================================= montage
def plan_index(t):
    idx = 0
    for k, p in enumerate(G["plans"]):
        if t >= p[0] - 1e-9:
            idx = k
    return idx


def dessiner_monde(ctx, t):
    idx = plan_index(t)
    debut = G["plans"][idx][0]
    if idx > 0 and t - debut < TRANSITION:
        u = (t - debut) / TRANSITION
        u = u * u * (3 - 2 * u)
        scene(ctx, t, G["plans"][idx - 1])
        r = u * math.hypot(W / 2, H / 2) * 1.05
        ctx.save()
        # transition : un cercle qui s'ouvre
        ctx.arc(W / 2, H / 2, max(r, 0.1), 0, 2 * math.pi)
        ctx.clip()
        scene(ctx, t, G["plans"][idx])
        ctx.restore()
        ctx.set_source_rgba(1, 1, 1, 0.9)
        ctx.set_line_width(26 * (1 - u) + 4)
        ctx.arc(W / 2, H / 2, max(r, 0.1), 0, 2 * math.pi)
        ctx.stroke()
    else:
        scene(ctx, t, G["plans"][idx])


def titre_rebondissant(draw, t, texte, y, taille, a):
    taille *= a
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
            ph = (tm(t) / C.NOIRE - k * 0.12) % 1
            dy = -22 * abs(math.sin(math.pi * ph))
            R.texte_contour(draw, (x + wl / 2, y + dy), c, taille, C.PALETTE[k % len(C.PALETTE)], ep=15)
        x += wl


def dessiner_textes(draw, t):
    debut_chant = G["lignes"][0]["debut"]
    if t < debut_chant + 1.0:
        a = min(1.0, t / 0.6) * min(1.0, max(0.0, (debut_chant + 1.0 - t) / 0.5))
        titre_rebondissant(draw, t, T.TITRE, 230, 130, a)
    fin = C.DUREE_TOTALE
    if t > fin - 3.0:
        u = min(1.0, (t - (fin - 3.0)) / 0.4)
        pop = 1 + 0.15 * math.sin(math.pi * min(1, u))
        R.texte_contour(draw, (W / 2, 300), "À bientôt !", 160 * u * pop, C.PALETTE[int(t * 4) % 7], ep=18)


def rendre_image(t):
    e = R.G["echelle"]
    w, h = int(W * e), int(H * e)
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    ctx = cairo.Context(s)
    ctx.scale(e, e)
    dessiner_monde(ctx, t)
    if t > C.DUREE_TOTALE - 1.0:
        ctx.set_source_rgba(0.1, 0.08, 0.3, min(1.0, (t - C.DUREE_TOTALE + 1.0)) * 0.85)
        ctx.paint()
    s.flush()
    a = np.ndarray((h, s.get_stride() // 4, 4), np.uint8, s.get_data())[:, :w, 2::-1]
    img = Image.fromarray(np.ascontiguousarray(a), "RGB")
    draw = ImageDraw.Draw(img)
    dessiner_textes(draw, t)
    R.dessiner_karaoke(draw, t)
    return img


def rendre_video(lignes, audio, sortie, dossier_tmp, echelle=1.0, processus=None, donnees=None):
    R.rendre_video(lignes, audio, sortie, dossier_tmp, echelle, processus, init=init_worker, image=rendre_image,
                   donnees=donnees)


# ======================================================================= miniature
def miniature(chemin):
    """Miniature YouTube 1920x1080 : décor de colline, personnages groupés, titre multicolore."""
    charger()
    G.setdefault("phase", 0.0)
    G.setdefault("chants", [])
    s = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    ctx = cairo.Context(s)
    dx = decalages(0.5)
    for c in ("ciel", "fond", "milieu"):
        couche(ctx, "colline", c, dx[c])
    ctx.set_source_rgba(1, 1, 1, 0.18)
    ctx.paint()
    pos = [("biquette", 470, 1010, 0.62, 0.0), ("hibou", 760, 1000, 0.6, 0.4), ("croco", 1180, 1010, 0.66, 0.2),
           ("cochon", 1470, 1020, 0.62, 0.6), ("lapin", 960, 1060, 0.74, 0.8)]
    for nom, x, y, e, ph in pos:
        ombre(ctx, x, y + 4, 150 * e)
        personnage(ctx, nom, x, y, e, 0.21, rebond=0, chant=True, yeux="ouverts", phase=ph,
                   bras=(70, -70), tete=0.0)
    couche(ctx, "colline", "devant", dx["devant"])
    s.flush()
    a = np.ndarray((H, s.get_stride() // 4, 4), np.uint8, s.get_data())[:, :W, 2::-1]
    img = Image.fromarray(np.ascontiguousarray(a), "RGB")
    draw = ImageDraw.Draw(img)
    for ligne, y in (("Toc toc toc,", 190), ("qui est là ?", 380)):
        f = R.police(200)
        larg = [f.getlength(c) for c in ligne]
        x = (W - sum(larg)) / 2
        for k, (c, wl) in enumerate(zip(ligne, larg)):
            if c != " ":
                dy = -18 * math.sin(k * 0.9)
                draw.text((x + wl / 2 + 8, y + dy + 12), c, font=f, fill=(58, 28, 92), anchor="ms",
                          stroke_width=26, stroke_fill=(58, 28, 92))
                draw.text((x + wl / 2, y + dy), c, font=f, fill=C.PALETTE[k % 7], anchor="ms",
                          stroke_width=20, stroke_fill=(255, 255, 255))
            x += wl
    img.save(chemin)

"""Décors animés dessinés avec cairo (dégradés pastel, soleil, nuages, étoiles…).

Un décor par section : aube, pré, grange, mare, nuit étoilée, forêt, fête, couchant.
Toutes les fonctions sont déterministes en fonction du temps t (secondes).
"""
import math
import random

import cairo

from . import config as C

W, H = C.LARGEUR, C.HAUTEUR
SOL = 840            # ligne de sol des personnages


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def melange(c1, c2, a):
    return tuple(x + (y - x) * a for x, y in zip(c1, c2))


# ------------------------------------------------------------------ primitives
def ciel(ctx, haut, bas, milieu=None):
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *haut)
    if milieu:
        g.add_color_stop_rgb(0.55, *milieu)
    g.add_color_stop_rgb(1, *bas)
    ctx.set_source(g)
    ctx.paint()


def cercle(ctx, x, y, r, couleur, alpha=1.0):
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.set_source_rgba(*couleur, alpha)
    ctx.fill()


def soleil(ctx, x, y, r, t, visage=True, couleur="#ffd23f"):
    # halo
    g = cairo.RadialGradient(x, y, r * 0.5, x, y, r * 2.4)
    g.add_color_stop_rgba(0, 1, 0.95, 0.6, 0.55)
    g.add_color_stop_rgba(1, 1, 0.95, 0.6, 0)
    ctx.set_source(g)
    ctx.arc(x, y, r * 2.4, 0, 2 * math.pi)
    ctx.fill()
    # rayons arrondis qui tournent
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(t * 0.4)
    ctx.set_source_rgb(*rgb("#ffb627"))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_width(r * 0.16)
    for k in range(12):
        a = k * math.pi / 6
        l = r * (1.25 + 0.12 * math.sin(t * 4 + k))
        ctx.move_to(math.cos(a) * r * 1.12, math.sin(a) * r * 1.12)
        ctx.line_to(math.cos(a) * l, math.sin(a) * l)
        ctx.stroke()
    ctx.restore()
    cercle(ctx, x, y, r, rgb(couleur))
    cercle(ctx, x - r * 0.25, y - r * 0.3, r * 0.45, (1, 1, 0.85), 0.35)
    if visage:
        brun = rgb("#7a4a1e")
        for dx in (-0.33, 0.33):
            cercle(ctx, x + dx * r, y - 0.1 * r, r * 0.1, brun)
            cercle(ctx, x + dx * r + r * 0.03, y - 0.14 * r, r * 0.035, (1, 1, 1))
        for dx in (-0.55, 0.55):
            cercle(ctx, x + dx * r, y + 0.15 * r, r * 0.13, rgb("#ff8a65"), 0.6)
        ctx.set_source_rgb(*brun)
        ctx.set_line_width(r * 0.07)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.arc(x, y + 0.12 * r, r * 0.33, 0.15 * math.pi, 0.85 * math.pi)
        ctx.stroke()


def nuage(ctx, x, y, s, alpha=1.0, couleur=(1, 1, 1)):
    bosses = [(-0.9, 0.15, 0.45), (-0.4, -0.15, 0.6), (0.25, -0.25, 0.7), (0.85, 0.05, 0.5),
              (0.0, 0.2, 0.55), (-0.5, 0.25, 0.45), (0.55, 0.25, 0.45)]
    # ombre douce
    for bx, by, br in bosses:
        cercle(ctx, x + bx * s, y + by * s + s * 0.12, br * s, (0.75, 0.82, 0.95), 0.35 * alpha)
    for bx, by, br in bosses:
        cercle(ctx, x + bx * s, y + by * s, br * s, couleur, alpha)


def nuages_defilants(ctx, t, n=5, y0=120, y1=380, vitesse=25, graine=3, alpha=1.0, couleur=(1, 1, 1)):
    rnd = random.Random(graine)
    for k in range(n):
        s = rnd.uniform(55, 95)
        y = rnd.uniform(y0, y1)
        x0 = rnd.uniform(0, W + 600)
        v = vitesse * rnd.uniform(0.6, 1.3)
        x = (x0 + t * v) % (W + 600) - 300
        nuage(ctx, x, y + 6 * math.sin(t * 0.8 + k), s, alpha, couleur)


def colline(ctx, y, amp, couleur, phase=0.0, longueur=900, couleur_haut=None):
    ctx.move_to(0, H)
    ctx.line_to(0, y)
    n = 24
    for i in range(n + 1):
        x = i * W / n
        ctx.line_to(x, y - amp * math.sin(x / longueur * math.pi * 2 + phase))
    ctx.line_to(W, H)
    ctx.close_path()
    if couleur_haut:
        g = cairo.LinearGradient(0, y - amp, 0, H)
        g.add_color_stop_rgb(0, *couleur_haut)
        g.add_color_stop_rgb(1, *couleur)
        ctx.set_source(g)
    else:
        ctx.set_source_rgb(*couleur)
    ctx.fill()


def rect_arrondi(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def grange(ctx, x, y, s, nuit=False):
    """Grange rouge, (x, y) = milieu du bas."""
    rouge = rgb("#e84a5f") if not nuit else rgb("#6a2c4a")
    toit = rgb("#a83246") if not nuit else rgb("#3e1b33")
    blanc = (1, 1, 1) if not nuit else rgb("#b9a9d6")
    w, h = 420 * s, 300 * s
    rect_arrondi(ctx, x - w / 2, y - h, w, h, 20 * s)
    ctx.set_source_rgb(*rouge)
    ctx.fill()
    # toit
    ctx.move_to(x - w / 2 - 30 * s, y - h + 10 * s)
    ctx.line_to(x - w / 4, y - h - 120 * s)
    ctx.line_to(x + w / 4, y - h - 120 * s)
    ctx.line_to(x + w / 2 + 30 * s, y - h + 10 * s)
    ctx.close_path()
    ctx.set_source_rgb(*toit)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.fill_preserve()
    ctx.set_line_width(14 * s)
    ctx.stroke()
    # porte
    pw, ph = 170 * s, 190 * s
    rect_arrondi(ctx, x - pw / 2, y - ph, pw, ph, 14 * s)
    ctx.set_source_rgb(*blanc)
    ctx.set_line_width(12 * s)
    ctx.stroke()
    ctx.move_to(x - pw / 2, y - ph)
    ctx.line_to(x + pw / 2, y)
    ctx.move_to(x + pw / 2, y - ph)
    ctx.line_to(x - pw / 2, y)
    ctx.stroke()
    # fenêtre ronde
    cercle(ctx, x, y - h - 30 * s, 38 * s, blanc)
    cercle(ctx, x, y - h - 30 * s, 28 * s, rgb("#ffe082") if nuit else rgb("#8fd3ff"))


def arbre(ctx, x, y, s, couleur="#4caf50", t=0.0):
    ctx.set_source_rgb(*rgb("#8d5a3b"))
    rect_arrondi(ctx, x - 22 * s, y - 170 * s, 44 * s, 170 * s, 18 * s)
    ctx.fill()
    c = rgb(couleur)
    clair = melange(c, (1, 1, 1), 0.25)
    sway = 6 * s * math.sin(t * 1.5 + x)
    for dx, dy, r in [(-60, -200, 80), (60, -200, 80), (0, -260, 95), (-30, -150, 70), (40, -150, 70)]:
        cercle(ctx, x + dx * s + sway, y + dy * s, r * s, c)
    cercle(ctx, x - 25 * s + sway, y - 285 * s, 40 * s, clair, 0.8)


def sapin(ctx, x, y, s, couleur="#2e7d32"):
    ctx.set_source_rgb(*rgb("#7b4f33"))
    ctx.rectangle(x - 15 * s, y - 50 * s, 30 * s, 50 * s)
    ctx.fill()
    c = rgb(couleur)
    for k, (w, h) in enumerate([(130, 120), (105, 110), (75, 95)]):
        yb = y - 40 * s - k * 70 * s
        ctx.move_to(x - w * s, yb)
        ctx.line_to(x, yb - h * s)
        ctx.line_to(x + w * s, yb)
        ctx.close_path()
        ctx.set_source_rgb(*c)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_width(24 * s)
        ctx.fill_preserve()
        ctx.stroke()


def fleur(ctx, x, y, s, couleur, t=0.0):
    ctx.set_source_rgb(*rgb("#43a047"))
    ctx.set_line_width(5 * s)
    ctx.move_to(x, y)
    ctx.line_to(x, y - 40 * s)
    ctx.stroke()
    yy = y - 40 * s
    a0 = t * 0.8
    for k in range(5):
        a = a0 + k * 2 * math.pi / 5
        cercle(ctx, x + math.cos(a) * 13 * s, yy + math.sin(a) * 13 * s, 10 * s, couleur)
    cercle(ctx, x, yy, 8 * s, rgb("#ffd54f"))


def barriere(ctx, x0, x1, y, s=1.0, couleur="#ffffff"):
    c = rgb(couleur)
    ctx.set_source_rgb(*c)
    for x in range(int(x0), int(x1), int(90 * s)):
        rect_arrondi(ctx, x, y - 110 * s, 26 * s, 110 * s, 10 * s)
        ctx.fill()
    for yy in (y - 85 * s, y - 45 * s):
        rect_arrondi(ctx, x0 - 10, yy, x1 - x0 + 20, 18 * s, 9 * s)
        ctx.fill()


def etoile(ctx, x, y, r, couleur=(1, 0.95, 0.6), alpha=1.0, rot=0.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rot)
    ctx.move_to(0, -r)
    for k in range(1, 10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.48
        ctx.line_to(math.cos(a) * rr, math.sin(a) * rr)
    ctx.close_path()
    ctx.set_source_rgba(*couleur, alpha)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_width(r * 0.3)
    ctx.fill_preserve()
    ctx.stroke()
    ctx.restore()


def etoiles_scintillantes(ctx, t, n=60, graine=7, y_max=650, alpha=1.0):
    rnd = random.Random(graine)
    for k in range(n):
        x, y = rnd.uniform(20, W - 20), rnd.uniform(20, y_max)
        r = rnd.uniform(6, 18)
        f = rnd.uniform(1.5, 3.5)
        ph = rnd.uniform(0, 6.28)
        sc = 0.55 + 0.45 * math.sin(t * f + ph)
        if r > 13:
            etoile(ctx, x, y, r * (0.7 + 0.3 * sc), alpha=alpha * (0.5 + 0.5 * sc), rot=0.2 * math.sin(t + k))
        else:
            cercle(ctx, x, y, r * 0.35 * (0.6 + 0.6 * sc), (1, 1, 0.9), alpha * (0.4 + 0.6 * sc))


def lune(ctx, x, y, r, t, ouverte=0.0):
    g = cairo.RadialGradient(x, y, r * 0.8, x, y, r * 2.2)
    g.add_color_stop_rgba(0, 1, 1, 0.85, 0.35)
    g.add_color_stop_rgba(1, 1, 1, 0.85, 0)
    ctx.set_source(g)
    ctx.arc(x, y, r * 2.2, 0, 2 * math.pi)
    ctx.fill()
    cercle(ctx, x, y, r, rgb("#fff4c2"))
    for dx, dy, rr in [(-0.35, 0.35, 0.12), (0.4, -0.45, 0.09), (0.45, 0.4, 0.07)]:
        cercle(ctx, x + dx * r, y + dy * r, rr * r, rgb("#f3e1a0"))
    brun = rgb("#7a5a2e")
    ctx.set_source_rgb(*brun)
    ctx.set_line_width(r * 0.06)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for dx in (-0.3, 0.3):     # yeux fermés, paisibles
        ctx.arc(x + dx * r, y - 0.1 * r, r * 0.13, 0.1 * math.pi, 0.9 * math.pi)
        ctx.stroke()
    if ouverte > 0.05:
        ctx.save()
        ctx.translate(x, y + 0.3 * r)
        ctx.scale(1, max(0.2, ouverte))
        cercle(ctx, 0, 0, r * 0.12, rgb("#a34a5a"))
        ctx.restore()
    else:
        ctx.arc(x, y + 0.2 * r, r * 0.15, 0.15 * math.pi, 0.85 * math.pi)
        ctx.stroke()
    for dx in (-0.5, 0.5):
        cercle(ctx, x + dx * r, y + 0.15 * r, r * 0.1, rgb("#ffab91"), 0.6)


def arc_en_ciel(ctx, x, y, r, epaisseur, alpha=0.85):
    couleurs = ["#ff5252", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#7e57c2"]
    ctx.set_line_width(epaisseur)
    for k, c in enumerate(couleurs):
        ctx.set_source_rgba(*rgb(c), alpha)
        ctx.arc(x, y, r - k * epaisseur, math.pi, 2 * math.pi)
        ctx.stroke()


def confettis(ctx, t, n=90, graine=11, intensite=1.0):
    rnd = random.Random(graine)
    pal = [rgb(h) for h in ("#ff5252", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#ab47bc", "#ff80ab")]
    for k in range(int(n * intensite)):
        x0 = rnd.uniform(0, W)
        v = rnd.uniform(90, 200)
        ph = rnd.uniform(0, H + 100)
        y = (ph + t * v) % (H + 100) - 50
        x = x0 + 30 * math.sin(t * rnd.uniform(1, 3) + k)
        c = pal[k % len(pal)]
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(t * rnd.uniform(-4, 4) + k)
        ctx.scale(1, abs(math.sin(t * 3 + k)) * 0.8 + 0.2)
        rect_arrondi(ctx, -9, -5, 18, 10, 4)
        ctx.set_source_rgb(*c)
        ctx.fill()
        ctx.restore()


def ballons(ctx, t, n=8, graine=5):
    rnd = random.Random(graine)
    pal = [rgb(h) for h in ("#ff5252", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#ab47bc", "#ff80ab")]
    for k in range(n):
        x0 = rnd.uniform(80, W - 80)
        v = rnd.uniform(50, 90)
        ph = rnd.uniform(0, H + 400)
        y = H + 200 - (ph + t * v) % (H + 400)
        x = x0 + 25 * math.sin(t * 1.2 + k)
        c = pal[k % len(pal)]
        ctx.set_source_rgba(0.4, 0.4, 0.4, 0.7)
        ctx.set_line_width(2)
        ctx.move_to(x, y + 62)
        ctx.curve_to(x + 10, y + 100, x - 10, y + 130, x, y + 170)
        ctx.stroke()
        ctx.save()
        ctx.translate(x, y)
        ctx.scale(1, 1.2)
        cercle(ctx, 0, 0, 50, c)
        cercle(ctx, -16, -18, 13, (1, 1, 1), 0.45)
        ctx.restore()


def fanions(ctx, t, y=40):
    pal = [rgb(h) for h in ("#ff5252", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#ab47bc", "#ff80ab")]
    ctx.set_source_rgb(0.45, 0.3, 0.25)
    ctx.set_line_width(4)
    ctx.move_to(0, y)
    ctx.curve_to(W / 3, y + 80, 2 * W / 3, y + 80, W, y)
    ctx.stroke()
    n = 16
    for k in range(n):
        u = (k + 0.5) / n
        x = u * W
        yy = y + 240 * u * (1 - u)          # point de la courbe de Bézier
        sw = 0.08 * math.sin(t * 3 + k)
        ctx.save()
        ctx.translate(x, yy)
        ctx.rotate(sw)
        ctx.move_to(-35, 0)
        ctx.line_to(35, 0)
        ctx.line_to(0, 70)
        ctx.close_path()
        ctx.set_source_rgb(*pal[k % len(pal)])
        ctx.fill()
        ctx.restore()


def mare(ctx, x, y, rx, ry, t):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(1, ry / rx)
    g = cairo.RadialGradient(0, 0, rx * 0.2, 0, 0, rx)
    g.add_color_stop_rgb(0, *rgb("#7fd8ff"))
    g.add_color_stop_rgb(1, *rgb("#3aa0e8"))
    ctx.arc(0, 0, rx, 0, 2 * math.pi)
    ctx.set_source(g)
    ctx.fill_preserve()
    ctx.set_source_rgb(*rgb("#a5d6a7"))
    ctx.set_line_width(26)
    ctx.stroke()
    # ronds dans l'eau
    for k in range(3):
        ph = (t * 0.5 + k / 3) % 1
        ctx.set_source_rgba(1, 1, 1, 0.6 * (1 - ph))
        ctx.set_line_width(5)
        ctx.arc(-rx * 0.35 + k * rx * 0.3, rx * 0.1 * (k - 1), 30 + ph * 120, 0, 2 * math.pi)
        ctx.stroke()
    ctx.restore()
    # nénuphars
    for dx, dy, r in [(-0.6, -0.1, 34), (0.55, 0.2, 28), (0.7, -0.35, 22)]:
        cx, cy = x + dx * rx, y + dy * ry
        ctx.save()
        ctx.translate(cx, cy + 3 * math.sin(t * 2 + dx * 5))
        ctx.scale(1, 0.55)
        ctx.move_to(0, 0)
        ctx.arc(0, 0, r, 0.3, 2 * math.pi - 0.3)
        ctx.close_path()
        ctx.set_source_rgb(*rgb("#66bb6a"))
        ctx.fill()
        ctx.restore()
    cercle(ctx, x - 0.6 * rx + 5, y - 0.1 * ry - 8, 10, rgb("#ff80ab"))


def roseaux(ctx, x, y, t, n=6):
    for k in range(n):
        xx = x + k * 22
        h = 150 + 35 * math.sin(k * 1.7)
        sw = 10 * math.sin(t * 1.3 + k)
        ctx.set_source_rgb(*rgb("#558b2f"))
        ctx.set_line_width(7)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(xx, y)
        ctx.curve_to(xx, y - h / 2, xx + sw, y - h * 0.8, xx + sw, y - h)
        ctx.stroke()
        ctx.save()
        ctx.translate(xx + sw, y - h)
        ctx.scale(1, 2.6)
        cercle(ctx, 0, 0, 9, rgb("#8d6e63"))
        ctx.restore()


def boue(ctx, x, y, rx, ry):
    ctx.save()
    ctx.translate(x, y)
    ctx.scale(1, ry / rx)
    cercle(ctx, 0, 0, rx, rgb("#8d6e63"))
    cercle(ctx, -rx * 0.3, -rx * 0.25, rx * 0.35, rgb("#a1887f"), 0.6)
    ctx.restore()


def champignon(ctx, x, y, s):
    ctx.set_source_rgb(*rgb("#fff3e0"))
    rect_arrondi(ctx, x - 14 * s, y - 45 * s, 28 * s, 45 * s, 10 * s)
    ctx.fill()
    ctx.save()
    ctx.translate(x, y - 45 * s)
    ctx.scale(1, 0.75)
    ctx.arc(0, 0, 45 * s, math.pi, 2 * math.pi)
    ctx.close_path()
    ctx.set_source_rgb(*rgb("#ef5350"))
    ctx.fill()
    ctx.restore()
    for dx, dy in [(-20, -60), (8, -70), (25, -55)]:
        cercle(ctx, x + dx * s, y + dy * s, 7 * s, (1, 1, 1))


def lucioles(ctx, t, n=25, graine=9):
    rnd = random.Random(graine)
    for k in range(n):
        x = rnd.uniform(0, W) + 40 * math.sin(t * rnd.uniform(0.3, 0.8) + k)
        y = rnd.uniform(500, 900) + 30 * math.cos(t * rnd.uniform(0.3, 0.8) + k * 2)
        a = 0.5 + 0.5 * math.sin(t * rnd.uniform(1.5, 3) + k)
        g = cairo.RadialGradient(x, y, 0, x, y, 22)
        g.add_color_stop_rgba(0, 1, 1, 0.6, 0.9 * a)
        g.add_color_stop_rgba(1, 1, 1, 0.6, 0)
        ctx.set_source(g)
        ctx.arc(x, y, 22, 0, 2 * math.pi)
        ctx.fill()


def pulse_ciel(t, base_haut, base_bas, amp=0.06):
    """Dégradé pastel qui « respire » doucement."""
    a = 0.5 + 0.5 * math.sin(t * 0.35)
    return (melange(base_haut, (1, 1, 1), amp * a), melange(base_bas, (1, 0.9, 0.95), amp * (1 - a)))


# ------------------------------------------------------------------ décors
def decor_aube(ctx, t, tl):
    p = min(1.0, tl / 7.5)
    haut = melange(rgb("#ffb6a3"), rgb("#9fd8ff"), p)
    bas = melange(rgb("#ffe5b4"), rgb("#e3f6ff"), p)
    ciel(ctx, haut, bas)
    soleil(ctx, 1500, 620 - 420 * (1 - (1 - p) ** 2), 110, t)
    nuages_defilants(ctx, t, n=4, graine=1, alpha=0.95)
    colline(ctx, 700, 40, rgb("#9ccc65"), 0.5, 1100, rgb("#aed581"))
    grange(ctx, 480, 760, 1.0)
    colline(ctx, 800, 25, rgb("#7cb342"), 2.0, 800, rgb("#8bc34a"))
    barriere(ctx, 1150, 1920, 880, 0.9)
    for k, c in enumerate(["#ff80ab", "#fff176", "#ce93d8", "#ff8a65", "#80deea"]):
        fleur(ctx, 120 + k * 230, 1000, 1.1, rgb(c), t + k)


def decor_pre(ctx, t, tl):
    haut, bas = pulse_ciel(t, rgb("#8fd3ff"), rgb("#e6f7ff"))
    ciel(ctx, haut, bas)
    soleil(ctx, 250, 200, 105, t)
    nuages_defilants(ctx, t, n=5, graine=2)
    colline(ctx, 650, 50, rgb("#9ccc65"), 1.0, 1300, rgb("#c5e1a5"))
    arbre(ctx, 1700, 690, 0.9, "#66bb6a", t)
    arbre(ctx, 1500, 700, 0.7, "#81c784", t)
    colline(ctx, 760, 30, rgb("#7cb342"), 0.2, 900, rgb("#9ccc65"))
    barriere(ctx, -20, 1940, 800, 0.85, "#fff8e1")
    for k in range(12):
        c = ["#ff80ab", "#fff176", "#ce93d8", "#ff8a65", "#80deea", "#ffffff"][k % 6]
        fleur(ctx, 60 + k * 165, 1010 - 30 * (k % 2), 1.0, rgb(c), t + k)


def decor_grange(ctx, t, tl):
    a = 0.5 + 0.5 * math.sin(t * 0.5)
    haut = melange(rgb("#ffc1e3"), rgb("#a5dcff"), a)
    bas = melange(rgb("#fff3c4"), rgb("#ffe0f0"), a)
    ciel(ctx, haut, bas)
    soleil(ctx, 1650, 190, 95, t)
    nuages_defilants(ctx, t, n=4, graine=4, vitesse=40)
    colline(ctx, 620, 45, rgb("#a5d66b"), 0.0, 1000, rgb("#c5e1a5"))
    grange(ctx, 960, 680, 1.25)
    colline(ctx, 720, 20, rgb("#7cb342"), 1.3, 700, rgb("#9ccc65"))
    # petites notes de musique qui s'envolent
    rnd = random.Random(13)
    for k in range(10):
        x0 = rnd.uniform(100, W - 100)
        ph = (t * 0.25 + k / 10) % 1
        x = x0 + 40 * math.sin(ph * 6.28 * 2 + k)
        y = 700 - ph * 650
        note_musique(ctx, x, y, 28, rgb(["#ff5252", "#42a5f5", "#ab47bc", "#ffa726", "#66bb6a"][k % 5]),
                     alpha=math.sin(ph * math.pi))


def note_musique(ctx, x, y, s, couleur, alpha=1.0):
    ctx.save()
    ctx.translate(x, y)
    ctx.set_source_rgba(*couleur, alpha)
    ctx.save()
    ctx.rotate(-0.4)
    ctx.scale(1, 0.75)
    ctx.arc(0, 0, s * 0.55, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()
    ctx.rectangle(s * 0.38, -s * 1.6, s * 0.14, s * 1.6)
    ctx.fill()
    ctx.move_to(s * 0.52, -s * 1.6)
    ctx.curve_to(s * 1.0, -s * 1.3, s * 1.0, -s * 0.9, s * 0.8, -s * 0.7)
    ctx.set_line_width(s * 0.14)
    ctx.stroke()
    ctx.restore()


def decor_mare(ctx, t, tl):
    haut, bas = pulse_ciel(t, rgb("#9ee6ff"), rgb("#eafff5"))
    ciel(ctx, haut, bas)
    soleil(ctx, 1680, 170, 90, t)
    nuages_defilants(ctx, t, n=5, graine=6)
    colline(ctx, 600, 40, rgb("#9ccc65"), 2.2, 1200, rgb("#c5e1a5"))
    sapin(ctx, 150, 640, 0.9, "#43a047")
    sapin(ctx, 300, 620, 0.7, "#2e7d32")
    colline(ctx, 700, 15, rgb("#8bc34a"), 0.3, 1600, rgb("#aed581"))
    mare(ctx, 560, 830, 430, 120, t)
    roseaux(ctx, 110, 860, t)
    roseaux(ctx, 920, 820, t, 4)
    boue(ctx, 1440, 850, 260, 55)
    for k in range(5):
        fleur(ctx, 1100 + k * 170, 1020, 1.0, rgb(["#ff80ab", "#fff176", "#ce93d8", "#ff8a65", "#80deea"][k]), t)


def decor_nuit(ctx, t, tl):
    ciel(ctx, rgb("#1a1446"), rgb("#5b3f8c"), rgb("#2e2470"))
    etoiles_scintillantes(ctx, t, n=80)
    lune(ctx, 1500, 230, 105, t)
    nuages_defilants(ctx, t, n=3, graine=8, vitesse=12, alpha=0.25, couleur=rgb("#c9c3ff"))
    colline(ctx, 690, 45, rgb("#2b3a67"), 0.8, 1200, rgb("#34497a"))
    grange(ctx, 380, 730, 0.8, nuit=True)
    colline(ctx, 790, 25, rgb("#223058"), 2.1, 800, rgb("#2b3d6b"))
    lucioles(ctx, t)


def decor_foret(ctx, t, tl):
    p = min(1.0, tl / 4)
    haut = melange(rgb("#ffd1dc"), rgb("#a6e3ff"), p)
    bas = melange(rgb("#fff1c1"), rgb("#f0fff0"), p)
    ciel(ctx, haut, bas)
    soleil(ctx, 960, 330 - 140 * p, 100, t)
    nuages_defilants(ctx, t, n=4, graine=10)
    colline(ctx, 600, 35, rgb("#a5d66b"), 1.5, 1000, rgb("#c5e1a5"))
    for k, (x, s, c) in enumerate([(80, 0.9, "#43a047"), (330, 1.1, "#66bb6a"), (1600, 1.0, "#4caf50"),
                                   (1850, 0.85, "#81c784"), (1380, 0.75, "#2e7d32")]):
        arbre(ctx, x, 700 + 10 * (k % 2), s, c, t)
    colline(ctx, 740, 20, rgb("#7cb342"), 0.7, 900, rgb("#9ccc65"))
    for x, s in [(560, 1.0), (620, 0.7), (1250, 0.9)]:
        champignon(ctx, x, 1000, s)
    for k in range(8):
        fleur(ctx, 80 + k * 250, 1040, 0.9, rgb(["#ff80ab", "#fff176", "#ce93d8", "#ff8a65"][k % 4]), t)


def decor_fete(ctx, t, tl, transpo=0):
    a = 0.5 + 0.5 * math.sin(t * 1.2)
    if transpo:
        haut = melange(rgb("#ffb3e6"), rgb("#ffd59e"), a)
        bas = melange(rgb("#d1f5ff"), rgb("#fff6b3"), a)
    else:
        haut = melange(rgb("#a5dcff"), rgb("#ffc6ec"), a)
        bas = melange(rgb("#fff6c9"), rgb("#e0ffe8"), a)
    ciel(ctx, haut, bas)
    arc_en_ciel(ctx, 960, 900, 820, 48)
    soleil(ctx, 1700, 180, 85, t * 1.5)
    nuages_defilants(ctx, t, n=4, graine=12, vitesse=50)
    ballons(ctx, t)
    colline(ctx, 680, 30, rgb("#a5d66b"), 0.4, 1000, rgb("#c5e1a5"))
    grange(ctx, 1580, 720, 0.75)
    colline(ctx, 760, 15, rgb("#7cb342"), 1.9, 700, rgb("#9ccc65"))
    fanions(ctx, t)


def decor_couchant(ctx, t, tl):
    p = min(1.0, tl / 8.7)
    ciel(ctx, melange(rgb("#ff9a8b"), rgb("#8e6bbf"), p), melange(rgb("#ffd194"), rgb("#ff9ab0"), p),
         melange(rgb("#ffb08a"), rgb("#d77fa1"), p))
    soleil(ctx, 960, 560 + 260 * p, 120, t, couleur="#ffb74d")
    etoiles_scintillantes(ctx, t, n=30, y_max=400, alpha=p)
    nuages_defilants(ctx, t, n=4, graine=14, vitesse=15, alpha=0.7, couleur=rgb("#ffe0ec"))
    colline(ctx, 700, 40, rgb("#7e9b5a"), 0.9, 1100, rgb("#9ab86c"))
    grange(ctx, 1600, 740, 0.85)
    colline(ctx, 790, 22, rgb("#5f7f45"), 2.4, 800, rgb("#76964f"))


DECORS = {
    "aube": decor_aube, "pre": decor_pre, "grange": decor_grange, "mare": decor_mare,
    "nuit": decor_nuit, "foret": decor_foret, "fete": decor_fete, "couchant": decor_couchant,
}

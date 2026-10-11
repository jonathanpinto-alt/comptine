"""Décors SVG de « Toc toc toc » : un décor par section, en couches pour la parallaxe.

Couches (2100 x 1080, un peu plus larges que l'écran pour le travelling) :
  ciel   : fond opaque (ciel ou mur du fond) ;
  fond   : éléments lointains (collines, fenêtres, étagères) ;
  milieu : maison, meubles, porte — les personnages se tiennent devant ;
  devant : petites choses au premier plan, sur les bords (fleurs, plantes).
La pluie, le feu, les étoiles qui scintillent, les confettis sont animés à part (cairo).
"""
import random

from .svg import CONTOUR, ell, ell_d, forme, plein, trait

LW, LH = 2100, 1080
SOL = 950            # ligne du sol (pieds des personnages)


def svg(contenu, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{LW}" height="{LH}" viewBox="0 0 {LW} {LH}">'
            f'<defs>{defs}</defs>{contenu}</svg>')


def degrade(id_, haut, bas):
    return (f'<linearGradient id="{id_}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{haut}"/>'
            f'<stop offset="1" stop-color="{bas}"/></linearGradient>')


def rect(x, y, w, h, couleur, **k):
    return forme(f"M{x},{y} L{x + w},{y} L{x + w},{y + h} L{x},{y + h} Z", couleur, **k)


def rect_arrondi(x, y, w, h, r, couleur, **k):
    d = (f"M{x + r},{y} L{x + w - r},{y} Q{x + w},{y} {x + w},{y + r} L{x + w},{y + h - r} "
         f"Q{x + w},{y + h} {x + w - r},{y + h} L{x + r},{y + h} Q{x},{y + h} {x},{y + h - r} "
         f"L{x},{y + r} Q{x},{y} {x + r},{y} Z")
    return forme(d, couleur, **k)


# ===================================================================== éléments
def nuage(x, y, s, couleur="#ffffff", opacite=1.0):
    d = (f"M{x - 110 * s},{y + 30 * s} Q{x - 130 * s},{y - 20 * s} {x - 70 * s},{y - 25 * s} "
         f"Q{x - 60 * s},{y - 80 * s} {x},{y - 70 * s} Q{x + 50 * s},{y - 105 * s} {x + 85 * s},{y - 45 * s} "
         f"Q{x + 140 * s},{y - 40 * s} {x + 120 * s},{y + 30 * s} Z")
    return f'<g opacity="{opacite}">{forme(d, couleur, ombre=0.08, reflet=0.0, ep=6)}</g>'


def colline(points_y, couleur, y_bas=LH, ep=7):
    """Ligne de collines douces passant par (x, y) puis fermée en bas."""
    d = f"M0,{y_bas} L0,{points_y[0][1]} "
    for (x0, y0), (x1, y1) in zip(points_y, points_y[1:]):
        cx = (x0 + x1) / 2
        d += f"C{cx},{y0} {cx},{y1} {x1},{y1} "
    d += f"L{LW},{y_bas} Z"
    return forme(d, couleur, ombre=0.1, reflet=0.12, ep=ep)


def arbre(x, y, s, feuillage="#4fbf5a", tronc="#9b6234"):
    t = rect(x - 22 * s, y - 150 * s, 44 * s, 150 * s, tronc, reflet=0)
    f = ell(x, y - 230 * s, 120 * s, 110 * s, feuillage) + ell(x - 70 * s, y - 180 * s, 70 * s, 60 * s, feuillage) \
        + ell(x + 75 * s, y - 175 * s, 70 * s, 60 * s, feuillage)
    for dx, dy in ((-40, -260), (30, -210), (60, -270), (-60, -200)):
        f += plein(ell_d(x + dx * s, y + dy * s, 10 * s, 10 * s), "#ff5c5c")
    return t + f


def sapin(x, y, s, couleur="#2f9e57"):
    res = rect(x - 18 * s, y - 60 * s, 36 * s, 60 * s, "#8b5a2b", reflet=0)
    for k, (w, h, dy) in enumerate(((140, 120, 60), (110, 110, 140), (80, 100, 215))):
        res += forme(f"M{x - w * s},{y - dy * s} L{x},{y - (dy + h + 40) * s} L{x + w * s},{y - dy * s} Z", couleur)
    return res


def fleur(x, y, couleur, s=1.0):
    res = trait(f"M{x},{y} L{x},{y - 45 * s}", "#3f9a3a", 6 * s)
    for k in range(5):
        import math
        a = k * 2 * math.pi / 5
        res += ell(x + 15 * s * math.cos(a), y - 50 * s + 15 * s * math.sin(a), 12 * s, 12 * s, couleur, ep=4, reflet=0.2)
    res += ell(x, y - 50 * s, 9 * s, 9 * s, "#ffd23f", ep=4)
    return res


def touffes(y, n, graine, couleur="#3fae4f"):
    rnd = random.Random(graine)
    res = ""
    for _ in range(n):
        x = rnd.uniform(0, LW)
        h = rnd.uniform(25, 50)
        res += forme(f"M{x - 25},{y} Q{x - 15},{y - h} {x - 5},{y - 10} Q{x},{y - h * 1.3} {x + 6},{y - 10} "
                     f"Q{x + 16},{y - h} {x + 25},{y} Z", couleur, reflet=0, ep=5)
    return res


def maisonnette(x, y, s, nuit=False):
    """Petite maison ronde du lapin (porte ronde, fenêtres éclairées, cheminée)."""
    mur = "#fff1d6" if not nuit else "#d9c7e6"
    toit = "#ef4b5f" if not nuit else "#a83b63"
    res = rect(x + 120 * s, y - 470 * s, 60 * s, 120 * s, "#c8694c")
    res += rect_arrondi(x - 220 * s, y - 330 * s, 440 * s, 330 * s, 30 * s, mur)
    res += forme(f"M{x - 270 * s},{y - 300 * s} Q{x},{y - 560 * s} {x + 270 * s},{y - 300 * s} Z", toit)
    res += forme(f"M{x - 55 * s},{y} L{x - 55 * s},{y - 130 * s} Q{x},{y - 200 * s} {x + 55 * s},{y - 130 * s} "
                 f"L{x + 55 * s},{y} Z", "#3fa36b")
    res += ell(x + 30 * s, y - 75 * s, 9 * s, 9 * s, "#ffd23f", ep=4)
    lum = "#ffd86b"
    for wx in (-150, 150):
        res += ell(x + wx * s, y - 175 * s, 50 * s, 50 * s, lum, reflet=0.4)
        res += trait(f"M{x + (wx - 50) * s},{y - 175 * s} L{x + (wx + 50) * s},{y - 175 * s} "
                     f"M{x + wx * s},{y - 225 * s} L{x + wx * s},{y - 125 * s}", CONTOUR, 6 * s)
    return res


def lune(x, y, r):
    res = ell(x, y, r, r, "#fff3b0", reflet=0.4)
    res += plein(ell_d(x - r * 0.3, y + r * 0.2, r * 0.15, r * 0.15), "#f0dc8a")
    res += plein(ell_d(x + r * 0.35, y - r * 0.25, r * 0.1, r * 0.1), "#f0dc8a")
    return res


def etoiles_fixes(n, graine, y_max):
    rnd = random.Random(graine)
    res = ""
    for _ in range(n):
        x, y, r = rnd.uniform(0, LW), rnd.uniform(0, y_max), rnd.uniform(3, 7)
        res += plein(ell_d(x, y, r, r), "#fff6c2", rnd.uniform(0.5, 1))
    return res


def mur_papier(couleur, rayure, id_):
    """Mur intérieur à rayures douces + plinthe + parquet."""
    res = f'<rect x="0" y="0" width="{LW}" height="{LH}" fill="{couleur}"/>'
    for x in range(0, LW, 90):
        res += f'<rect x="{x}" y="0" width="40" height="{SOL - 120}" fill="{rayure}" opacity="0.5"/>'
    for x in range(30, LW, 90):
        for y in range(60, SOL - 160, 120):
            res += plein(ell_d(x + 35, y + (x // 90 % 2) * 60, 7, 7), "#ffffff", 0.5)
    res += f'<rect x="0" y="{SOL - 120}" width="{LW}" height="20" fill="#ffffff"/>'
    res += f'<rect x="0" y="{SOL - 100}" width="{LW}" height="{LH - SOL + 100}" fill="#d98c4f"/>'
    for k in range(0, LW, 160):
        res += trait(f"M{k},{SOL - 100} L{k - 120},{LH}", "#c27a40", 5)
    for y in (SOL - 40, SOL + 40, SOL + 110):
        res += trait(f"M0,{y} L{LW},{y}", "#c27a40", 4)
    return res


def fenetre(x, y, w, h, ciel_haut, ciel_bas, id_, nuit=False, pluie=True):
    defs = degrade(id_, ciel_haut, ciel_bas)
    res = rect_arrondi(x - 25, y - 25, w + 50, h + 50, 20, "#ffffff")
    res += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{id_})" stroke="{CONTOUR}" stroke-width="6"/>'
    if nuit:
        res += lune(x + w * 0.72, y + h * 0.28, h * 0.12)
    else:
        res += nuage(x + w * 0.3, y + h * 0.3, 0.6, "#c9d3ec") + nuage(x + w * 0.75, y + h * 0.4, 0.5, "#b7c2e0")
    if pluie:
        rnd = random.Random(x)
        for _ in range(int(w * h / 3000)):
            px, py = rnd.uniform(x + 10, x + w - 10), rnd.uniform(y + 10, y + h - 30)
            res += trait(f"M{px},{py} l-6,22", "#e6f3ff", 3, 'opacity="0.8"')
    res += trait(f"M{x + w / 2},{y} L{x + w / 2},{y + h} M{x},{y + h / 2} L{x + w},{y + h / 2}", "#ffffff", 14)
    res += trait(f"M{x + w / 2},{y} L{x + w / 2},{y + h} M{x},{y + h / 2} L{x + w},{y + h / 2}", CONTOUR, 3)
    # rideaux
    for cx, s_ in ((x - 30, 1), (x + w + 30, -1)):
        res += forme(f"M{cx - 40 * s_},{y - 50} L{cx + 70 * s_},{y - 50} Q{cx + 30 * s_},{y + h / 2} {cx + 60 * s_},{y + h + 40} "
                     f"L{cx - 40 * s_},{y + h + 40} Z", "#ff7fa6")
    res += rect_arrondi(x - 90, y - 70, w + 180, 26, 13, "#b06a3a")
    return res, defs


def cadre(x, y, w, h, couleur):
    res = rect_arrondi(x, y, w, h, 12, "#ffd23f")
    res += rect(x + 18, y + 18, w - 36, h - 36, couleur, reflet=0.2, ep=5)
    return res


def guirlande(y, x0=0, x1=LW, graine=1):
    cols = ["#ff5252", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#ab47bc", "#ff80ab"]
    res = trait(f"M{x0},{y} Q{(x0 + x1) / 2},{y + 90} {x1},{y}", CONTOUR, 5)
    n = int((x1 - x0) / 110)
    for k in range(n):
        u = (k + 0.5) / n
        x = x0 + (x1 - x0) * u
        yy = y + 90 * 2 * u * (1 - u) * 2 * 0.5 * 2
        res += forme(f"M{x - 35},{yy} L{x + 35},{yy} L{x},{yy + 70} Z", cols[k % 7], reflet=0.2, ep=5)
    return res


def porte_ronde(x, y, w, h, couleur, ouverte=False):
    d = f"M{x - w / 2},{y} L{x - w / 2},{y - h + w / 2} Q{x - w / 2},{y - h} {x},{y - h} Q{x + w / 2},{y - h} " \
        f"{x + w / 2},{y - h + w / 2} L{x + w / 2},{y} Z"
    res = forme(d, "#ffffff", ombre=0, reflet=0, ep=EP_CADRE, extra="")
    if not ouverte:
        res += forme(d, couleur)
        for k in (-1, 1):
            res += trait(f"M{x + k * w / 4},{y - 30} L{x + k * w / 4},{y - h + w / 2.5}", "#00000022", 8)
        res += ell(x + w * 0.32, y - h * 0.45, 13, 13, "#ffd23f")
        res += ell(x, y - h * 0.62, 26, 26, "#ffd23f", reflet=0.4)          # heurtoir
    return res


EP_CADRE = 26


def fauteuil(x, y, couleur):
    res = rect_arrondi(x - 150, y - 260, 300, 200, 70, couleur)
    res += rect_arrondi(x - 190, y - 160, 380, 120, 50, couleur)
    for k in (-1, 1):
        res += rect_arrondi(x + k * 175 - 45, y - 200, 90, 170, 40, couleur)
    res += rect(x - 150, y - 40, 20, 40, "#8b5a2b", reflet=0) + rect(x + 130, y - 40, 20, 40, "#8b5a2b", reflet=0)
    return res


def cheminee(x, y):
    res = rect(x - 210, y - 380, 420, 380, "#d96b52")
    for yy in range(int(y - 350), int(y), 45):
        res += trait(f"M{x - 210},{yy} L{x + 210},{yy}", "#b9523d", 4)
    res += rect_arrondi(x - 250, y - 410, 500, 50, 15, "#ffffff")
    res += forme(f"M{x - 120},{y} L{x - 120},{y - 160} Q{x},{y - 280} {x + 120},{y - 160} L{x + 120},{y} Z", "#3a2340",
                 ombre=0, reflet=0)
    res += rect(x - 100, y - 40, 200, 30, "#8b5a2b", reflet=0)
    # objets sur la cheminée
    res += ell(x - 150, y - 450, 30, 40, "#7fd8ff") + rect(x + 110, y - 500, 70, 90, "#ffd23f")
    res += ell(x + 145, y - 455, 22, 22, "#ffffff", reflet=0)
    return res


def tapis(x, y, couleur):
    return ell(x, y, 420, 60, couleur, reflet=0.1) + ell(x, y, 330, 42, "#ffffff", ombre=0, reflet=0, contour=False) \
        + ell(x, y, 300, 36, couleur, ombre=0, reflet=0, contour=False)


# ===================================================================== décors
def ciel_degrade(haut, bas, extra=""):
    return svg(f'<rect x="0" y="0" width="{LW}" height="{LH}" fill="url(#ciel)"/>' + extra, degrade("ciel", haut, bas))


def colline_couches(nuit=False):
    if nuit:
        ciel = ciel_degrade("#1c1e5a", "#5c4a9c", etoiles_fixes(90, 3, 600) + lune(1650, 190, 90))
    else:
        ciel = ciel_degrade("#7f8fd9", "#d6c2f0", nuage(400, 180, 1.2, "#c7cbe8") + nuage(1300, 140, 1.0, "#b9bfe2")
                            + nuage(1850, 230, 0.9, "#c7cbe8"))
    fond = colline([(0, 700), (500, 620), (1000, 700), (1500, 610), (2100, 690)], "#6fae8f" if not nuit else "#3c5f7a")
    fond += sapin(250, 690, 1.0, "#2f8f63" if not nuit else "#264d5a") + sapin(1750, 680, 0.9, "#2f8f63" if not nuit else "#264d5a")
    milieu = colline([(0, 850), (600, 760), (1050, 700), (1500, 770), (2100, 860)], "#7cc86b" if not nuit else "#4f7d6a")
    milieu += maisonnette(1050, 760, 0.95, nuit)
    milieu += arbre(450, 860, 1.1, "#4fbf5a" if not nuit else "#35705a") + arbre(1650, 860, 1.0, "#5ccf6a" if not nuit else "#3d7a62")
    devant = touffes(1080, 30, 5, "#3fae4f" if not nuit else "#2f6b55")
    for k, c in enumerate(("#ff6fa5", "#ffd23f", "#ffffff", "#b388ff", "#ff8a65")):
        devant += fleur(120 + k * 70, 1070, c, 1.4) + fleur(1780 + k * 65, 1070, c, 1.3)
    return dict(ciel=ciel, fond=svg(fond), milieu=svg(milieu), devant=svg(devant))


def cuisine():
    ciel = svg(mur_papier("#ffe7a8", "#ffd77a", "m"))
    f, defs = fenetre(1300, 180, 420, 360, "#7f8fd9", "#c9cdec", "vit")
    f += rect_arrondi(250, 300, 420, 22, 10, "#b06a3a")
    for k, c in enumerate(("#ff6fa5", "#7fd8ff", "#7ce08a", "#ffab6b")):
        f += rect_arrondi(275 + k * 100, 200, 70, 100, 18, c) + rect(285 + k * 100, 185, 50, 22, "#ffffff", reflet=0, ep=5)
    f += cadre(750, 230, 220, 180, "#a8e0ff")
    f += ell(860, 330, 50, 40, "#ffd23f") + ell(860, 330, 20, 20, "#ff8a65", contour=False)
    fond = svg(f, defs)
    # cuisinière et table
    m = rect_arrondi(220, SOL - 360, 330, 360, 20, "#7fd8ff")
    m += rect(250, SOL - 300, 270, 180, "#3a2340", ombre=0, reflet=0.1)
    m += ell(300, SOL - 375, 50, 14, "#3a2340", ombre=0, reflet=0, contour=False) + ell(470, SOL - 375, 50, 14, "#3a2340", ombre=0, reflet=0, contour=False)
    m += rect_arrondi(280, SOL - 500, 160, 120, 30, "#ff5c5c") + rect(260, SOL - 520, 200, 26, "#ff5c5c")
    m += rect_arrondi(1500, SOL - 230, 420, 40, 10, "#ffffff")
    for x0 in range(1500, 1920, 60):
        m += rect(x0, SOL - 230, 30, 40, "#ff7fa6", ombre=0, reflet=0, contour=False)
    m += rect(1530, SOL - 190, 26, 190, "#b06a3a", reflet=0) + rect(1864, SOL - 190, 26, 190, "#b06a3a", reflet=0)
    m += ell(1620, SOL - 255, 40, 25, "#ffd23f") + ell(1770, SOL - 250, 30, 20, "#ff8a65")
    devant = svg(forme("M0,1080 L0,980 Q80,940 140,1080 Z", "#4fbf5a") + rect_arrondi(1950, 920, 120, 160, 30, "#ff8a65"))
    return dict(ciel=ciel, fond=fond, milieu=svg(m), devant=devant)


def salon(fete=False):
    ciel = svg(mur_papier("#c9f0d8", "#a8e6c0", "s"))
    f = cadre(260, 160, 240, 200, "#ffd8e6") + cadre(560, 200, 180, 150, "#cfe8ff")
    f += ell(380, 260, 50, 50, "#ffd23f", reflet=0.3)
    f += cheminee(1500, SOL - 110)
    if fete:
        f += guirlande(60, 0, LW) + guirlande(120, 300, 1800, 2)
    else:
        f += guirlande(80, 600, 1300)
    m = fauteuil(330, SOL - 40, "#9b59d0") + tapis(1050, SOL + 30, "#ff8a65" if not fete else "#ffd23f")
    if fete:
        m += rect_arrondi(780, SOL - 190, 520, 30, 12, "#ffffff")
        m += rect(800, SOL - 160, 24, 160, "#b06a3a", reflet=0) + rect(1256, SOL - 160, 24, 160, "#b06a3a", reflet=0)
    devant = svg(rect_arrondi(-20, 900, 160, 200, 40, "#ffab6b") + ell(60, 850, 90, 90, "#4fbf5a")
                 + rect_arrondi(1970, 880, 150, 220, 40, "#7fd8ff") + ell(2040, 830, 80, 90, "#5ccf6a"))
    return dict(ciel=ciel, fond=svg(f), milieu=svg(m), devant=devant)


def porte_exterieur():
    ciel = ciel_degrade("#6f7fcf", "#b9b2e8", nuage(300, 150, 1.1, "#aeb4dc") + nuage(1700, 120, 1.0, "#aeb4dc"))
    # intérieur chaud visible par la porte ouverte (derrière le lapin)
    f = rect(900, 380, 300, 520, "#ffcf6b", reflet=0) + rect(900, 380, 300, 520, "#ff9a5c", ombre=0.3, reflet=0, contour=False)
    fond = svg(f)
    facade = f'<path d="M0,0 L{LW},0 L{LW},{SOL} L0,{SOL} Z M900,{SOL - 50} L900,520 Q1050,330 1200,520 L1200,{SOL - 50} Z" fill="#fff1d6" fill-rule="evenodd"/>'
    for y in range(80, SOL, 110):
        facade += trait(f"M0,{y} L880,{y} M1220,{y} L{LW},{y}", "#f0dcb5", 5)
    facade += f'<path d="M900,{SOL - 50} L900,520 Q1050,330 1200,520 L1200,{SOL - 50}" fill="none" stroke="#3fa36b" stroke-width="40"/>'
    facade += trait(f"M900,{SOL - 50} L900,520 Q1050,330 1200,520 L1200,{SOL - 50}", CONTOUR, 6)
    facade += forme(f"M1200,{SOL - 50} L1200,520 Q1280,560 1330,{SOL - 70} L1330,{SOL} Z", "#3fa36b")   # battant ouvert
    facade += ell(1290, 700, 12, 12, "#ffd23f")
    facade += forme("M0,0 L2100,0 L2100,60 Q1050,140 0,60 Z", "#ef4b5f")                                # bord du toit
    facade += rect(1380, 280, 60, 90, "#ffd86b", reflet=0.5) + rect(1370, 260, 80, 25, "#3a2340", reflet=0)
    facade += rect_arrondi(820, SOL - 60, 460, 70, 20, "#c9b8a6")                                       # marche
    facade += f'<rect x="0" y="{SOL}" width="{LW}" height="{LH - SOL}" fill="#9fcf7a"/>'
    facade += trait(f"M0,{SOL} L{LW},{SOL}", CONTOUR, 6)
    for x, c in ((200, "#ff6fa5"), (1550, "#ffd23f"), (1850, "#b388ff")):
        facade += rect_arrondi(x - 70, SOL - 140, 140, 140, 25, "#ff8a65") + ell(x, SOL - 160, 85, 60, "#4fbf5a")
        facade += fleur(x - 35, SOL - 150, c, 1.2) + fleur(x + 35, SOL - 155, c, 1.2)
    devant = svg(ell(400, 1030, 160, 30, "#8fc3ff", reflet=0.4, ep=5) + ell(1650, 1050, 200, 32, "#8fc3ff", reflet=0.4, ep=5))
    return dict(ciel=ciel, fond=fond, milieu=svg(facade), devant=devant)


def fenetre_nuit():
    ciel = svg(mur_papier("#5a4f9c", "#6a5fb0", "n"))
    f, defs = fenetre(700, 160, 700, 520, "#1c1e5a", "#4a3f8f", "vitn", nuit=True)
    fond = svg(f, defs)
    m = fauteuil(1700, SOL - 40, "#ff7fa6") + tapis(1000, SOL + 40, "#ffb36b")
    m += cheminee(330, SOL - 110)
    devant = svg(rect_arrondi(1980, 900, 140, 200, 40, "#7fd8ff"))
    return dict(ciel=ciel, fond=fond, milieu=svg(m), devant=devant)


def porte_nuit_couches():
    ciel = svg(mur_papier("#6c5aa8", "#7a68b8", "pn"))
    nuitd = degrade("dn", "#141648", "#3d3480")
    fond = svg(f'<path d="M900,{SOL - 20} L900,420 Q1050,250 1200,420 L1200,{SOL - 20} Z" fill="url(#dn)"/>'
               + etoiles_fixes(14, 9, 0), nuitd)
    m = f'<path d="M0,0 L{LW},0 L{LW},{LH} L0,{LH} Z M900,{SOL - 20} L900,420 Q1050,250 1200,420 L1200,{SOL - 20} Z" fill="none"/>'
    m += f'<path d="M900,{SOL - 20} L900,420 Q1050,250 1200,420 L1200,{SOL - 20}" fill="none" stroke="#ffffff" stroke-width="36"/>'
    m += trait(f"M900,{SOL - 20} L900,420 Q1050,250 1200,420 L1200,{SOL - 20}", CONTOUR, 6)
    m += fauteuil(380, SOL - 40, "#9b59d0")
    m += rect(1500, 300, 50, 120, "#ffd86b", reflet=0.5) + rect(1490, 280, 70, 25, "#3a2340", reflet=0)
    m += cadre(1650, 200, 200, 160, "#cfe8ff") + tapis(1050, SOL + 30, "#ff8a65")
    return dict(ciel=ciel, fond=fond, milieu=svg(m), devant=svg(""))


_FABRIQUES = {
    "colline": lambda: colline_couches(False), "colline_nuit": lambda: colline_couches(True),
    "cuisine": cuisine, "salon": lambda: salon(False), "fete": lambda: salon(True),
    "porte": porte_exterieur, "fenetre": fenetre_nuit, "porte_nuit": porte_nuit_couches,
}


def _couches(nom):
    cache = {}

    def get(couche):
        if not cache:
            cache.update(_FABRIQUES[nom]())
        return cache[couche]
    return {c: (lambda c=c: get(c)) for c in ("ciel", "fond", "milieu", "devant")}


DECORS = {nom: _couches(nom) for nom in _FABRIQUES}

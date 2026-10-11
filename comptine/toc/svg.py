"""Dessins SVG de « Toc toc toc » : personnages découpés en pièces riggées, accessoires.

Chaque personnage est dessiné dans un cadre de 600 x 720 (pieds à y = 700) et
découpé en pièces : queue, oreilles, bras, corps, tête, yeux (ouverts/fermés),
bouche (fermée/ouverte), accessoires. Chaque pièce a un pivot (point de rotation)
et un parent (corps ou tête). Les pièces sont écrites en .svg dans
assets/toc/svg/, puis rastérisées une fois (cairosvg) pour l'animation.

Style : aplats saturés et chauds, contour net prune foncé, ombre douce et petit
reflet à l'intérieur de chaque forme (clipPath), gros yeux brillants, joues roses.
"""
import itertools

CONTOUR = "#3a2340"
EP = 7
_ids = itertools.count()


def _id(p):
    return f"{p}{next(_ids)}"


# ===================================================================== primitives
def forme(d, couleur, ombre=0.13, reflet=0.22, contour=True, ep=EP, extra=""):
    """Forme pleine (chemin `d`) avec ombre douce en bas à droite et reflet en haut à gauche."""
    cid = _id("c")
    gid = _id("g")
    s = f'<clipPath id="{cid}"><path d="{d}"/></clipPath>'
    s += f'<path d="{d}" fill="{couleur}" {extra}/>'
    if ombre:
        s += (f'<radialGradient id="{gid}" cx="0.3" cy="0.25" r="0.9">'
              f'<stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
              f'<stop offset="1" stop-color="#2a0f30" stop-opacity="{ombre}"/></radialGradient>')
        s += f'<path d="{d}" fill="url(#{gid})" clip-path="url(#{cid})"/>'
    if reflet:
        hid = _id("h")
        s += (f'<radialGradient id="{hid}" cx="0.32" cy="0.22" r="0.35">'
              f'<stop offset="0" stop-color="#fff" stop-opacity="{reflet}"/>'
              f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>')
        s += f'<path d="{d}" fill="url(#{hid})" clip-path="url(#{cid})"/>'
    if contour:
        s += f'<path d="{d}" fill="none" stroke="{CONTOUR}" stroke-width="{ep}" stroke-linejoin="round"/>'
    return s


def ell_d(cx, cy, rx, ry):
    return (f"M{cx - rx},{cy} A{rx},{ry} 0 1,0 {cx + rx},{cy} A{rx},{ry} 0 1,0 {cx - rx},{cy} Z")


def ell(cx, cy, rx, ry, couleur, rot=0, **k):
    s = forme(ell_d(cx, cy, rx, ry), couleur, **k)
    return f'<g transform="rotate({rot} {cx} {cy})">{s}</g>' if rot else s


def trait(d, couleur=CONTOUR, ep=EP, extra=""):
    return f'<path d="{d}" fill="none" stroke="{couleur}" stroke-width="{ep}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'


def plein(d, couleur, opacite=1.0):
    return f'<path d="{d}" fill="{couleur}" opacity="{opacite}"/>'


def svg(contenu, w=600, h=720):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'{contenu}</svg>')


# ===================================================================== visage
def yeux_ouverts(xg=245, xd=355, y=268, rx=36, ry=44, iris="#2b1a2e", anneau=None):
    s = ""
    for x in (xg, xd):
        if anneau:
            s += ell(x, y, rx + 18, ry + 16, anneau, reflet=0.3)
        s += ell(x, y, rx, ry, "#ffffff", ombre=0.06, reflet=0)
        s += ell(x + 4, y + 6, rx * 0.68, ry * 0.72, iris, ombre=0, reflet=0, contour=False)
        s += plein(ell_d(x - rx * 0.12, y - ry * 0.22, rx * 0.26, ry * 0.24), "#ffffff")
        s += plein(ell_d(x + rx * 0.3, y + ry * 0.3, rx * 0.11, ry * 0.1), "#ffffff", 0.9)
    return s


def yeux_fermes(xg=245, xd=355, y=272, rx=36):
    s = ""
    for x in (xg, xd):
        s += trait(f"M{x - rx * 0.8},{y - 4} Q{x},{y + 22} {x + rx * 0.8},{y - 4}", ep=8)
    return s


def joues(xg=212, xd=388, y=335, r=27):
    return "".join(plein(ell_d(x, y, r, r * 0.62), "#ff8fb0", 0.75) for x in (xg, xd))


def bouche_fermee(x=300, y=348, l=36):
    return trait(f"M{x - l},{y} Q{x},{y + 34} {x + l},{y}", ep=8)


def bouche_ouverte(x=300, y=345, l=36, h=50):
    d = f"M{x - l},{y} Q{x},{y + 8} {x + l},{y} Q{x + l * 0.9},{y + h} {x},{y + h + 4} Q{x - l * 0.9},{y + h} {x - l},{y} Z"
    s = forme(d, "#8c1d3a", ombre=0, reflet=0, ep=7)
    s += plein(ell_d(x, y + h * 0.72, l * 0.55, h * 0.26), "#ff7f9b")
    return s


def bras(x0, y0, x1, y1, couleur, main=None, ep=40):
    """Bras arrondi (épaule -> main) avec contour, et une main ronde."""
    main = main or couleur
    s = trait(f"M{x0},{y0} L{x1},{y1}", CONTOUR, ep + 2 * EP)
    s += trait(f"M{x0},{y0} L{x1},{y1}", couleur, ep)
    s += ell(x1, y1, ep * 0.72, ep * 0.72, main, reflet=0.15)
    return s


def pieds(couleur, y=688, ecart=48, rx=46, ry=24):
    return ell(300 - ecart, y, rx, ry, couleur) + ell(300 + ecart, y, rx, ry, couleur)


# ===================================================================== personnages
def lapin():
    fourrure, rose, robe = "#fff6ec", "#ffb3c9", "#ef4b5f"
    p = {}
    for nom, x, rot in (("oreille_g", 252, -10), ("oreille_d", 348, 10)):
        s = ell(x, 85, 36, 100, fourrure, rot=rot) + ell(x, 95, 18, 72, rose, rot=rot, ombre=0, contour=False)
        p[nom] = dict(svg=s, pivot=(x, 170), parent="tete", z=1)
    corps = pieds(fourrure)
    corps += forme("M205,460 Q300,410 395,460 L425,660 Q300,700 175,660 Z", robe)
    for x, y in ((240, 520), (330, 500), (360, 600), (260, 615), (300, 560), (210, 590), (385, 545)):
        corps += plein(ell_d(x, y, 11, 11), "#ffffff", 0.9)
    corps += forme("M245,500 Q300,485 355,500 L370,640 Q300,665 230,640 Z", "#ffd84d", ombre=0.08)
    corps += trait("M255,505 Q300,520 345,505", "#ffffff", 5)
    p["corps"] = dict(svg=corps, pivot=(300, 690), parent=None, z=3)
    p["bras_g"] = dict(svg=bras(225, 470, 160, 585, fourrure), pivot=(225, 470), parent="corps", z=4)
    p["bras_d"] = dict(svg=bras(375, 470, 440, 585, fourrure), pivot=(375, 470), parent="corps", z=4)
    tete = ell(300, 280, 152, 140, fourrure)
    tete += plein(ell_d(300, 312, 16, 12), "#ff7fa6") + trait("M300,322 L300,336", ep=5)
    tete += trait("M215,318 L165,308 M215,330 L165,336 M385,318 L435,308 M385,330 L435,336", "#c9a8a0", 4)
    tete += joues()
    p["tete"] = dict(svg=tete, pivot=(300, 420), parent="corps", z=5)
    noeud = forme("M228,168 L188,140 L190,196 Z", "#ff5c93") + forme("M228,168 L268,140 L266,196 Z", "#ff5c93")
    noeud += ell(228, 168, 14, 14, "#ff2f74")
    p["noeud"] = dict(svg=noeud, pivot=(300, 420), parent="tete", z=7)
    p["yeux_ouverts"] = dict(svg=yeux_ouverts(), pivot=(300, 420), parent="tete", z=6)
    p["yeux_fermes"] = dict(svg=yeux_fermes(), pivot=(300, 420), parent="tete", z=6)
    dents = forme("M290,342 L310,342 L310,360 L290,360 Z", "#ffffff", ombre=0, reflet=0, ep=4)
    p["bouche_fermee"] = dict(svg=bouche_fermee(y=345) + dents, pivot=(300, 420), parent="tete", z=6)
    p["bouche_ouverte"] = dict(svg=bouche_ouverte(y=342) + dents, pivot=(300, 420), parent="tete", z=6)
    return p


def cochon():
    rose, fonce, bleu = "#ffa3c0", "#ff7aa6", "#3d7be0"
    p = {}
    p["queue"] = dict(svg=trait("M395,600 q40,-10 40,-40 q0,-25 -20,-20 q-15,10 5,25 q25,10 40,-15", CONTOUR, 14)
                      + trait("M395,600 q40,-10 40,-40 q0,-25 -20,-20 q-15,10 5,25 q25,10 40,-15", fonce, 7),
                      pivot=(395, 600), parent="corps", z=0)
    for nom, x, s_ in (("oreille_g", 185, -1), ("oreille_d", 415, 1)):
        d = f"M{x - 30 * s_},{185} L{x + 38 * s_},{105} L{x + 52 * s_},{205} Z"
        p[nom] = dict(svg=forme(d, rose) + plein(f"M{x - 5 * s_},{180} L{x + 33 * s_},{132} L{x + 40 * s_},{190} Z", fonce, 0.8),
                      pivot=(x + 10 * s_, 195), parent="tete", z=1)
    corps = pieds(fonce)
    corps += ell(300, 545, 120, 130, rose)
    corps += forme("M195,560 Q300,540 405,560 L410,640 Q300,700 190,640 Z", bleu)
    corps += forme("M235,470 L262,470 L262,560 L235,560 Z", bleu, reflet=0) + forme("M338,470 L365,470 L365,560 L338,560 Z", bleu, reflet=0)
    corps += ell(249, 560, 11, 11, "#ffd23f") + ell(351, 560, 11, 11, "#ffd23f")
    corps += forme("M270,585 L330,585 L330,625 L270,625 Z", "#5d97f0", ombre=0, reflet=0, ep=5)
    p["corps"] = dict(svg=corps, pivot=(300, 690), parent=None, z=3)
    p["bras_g"] = dict(svg=bras(205, 480, 150, 590, rose, fonce), pivot=(205, 480), parent="corps", z=4)
    p["bras_d"] = dict(svg=bras(395, 480, 450, 590, rose, fonce), pivot=(395, 480), parent="corps", z=4)
    tete = ell(300, 290, 158, 140, rose)
    tete += ell(300, 322, 54, 38, fonce, reflet=0.3)
    tete += plein(ell_d(282, 322, 9, 14), "#9c2d55") + plein(ell_d(318, 322, 9, 14), "#9c2d55")
    tete += joues(205, 395, 330)
    p["tete"] = dict(svg=tete, pivot=(300, 425), parent="corps", z=5)
    p["yeux_ouverts"] = dict(svg=yeux_ouverts(240, 360, 245, 32, 38), pivot=(300, 425), parent="tete", z=6)
    p["yeux_fermes"] = dict(svg=yeux_fermes(240, 360, 248, 32), pivot=(300, 425), parent="tete", z=6)
    p["bouche_fermee"] = dict(svg=bouche_fermee(300, 375, 34), pivot=(300, 425), parent="tete", z=6)
    p["bouche_ouverte"] = dict(svg=bouche_ouverte(300, 372, 34, 42), pivot=(300, 425), parent="tete", z=6)
    return p


def biquette():
    poil, beige, corne, robe = "#f7f2ea", "#e8d2b6", "#c99a62", "#46c06a"
    p = {}
    for nom, x, s_ in (("oreille_g", 160, -1), ("oreille_d", 440, 1)):
        p[nom] = dict(svg=ell(x, 255, 62, 26, poil, rot=s_ * 22) + ell(x + 6 * s_, 257, 38, 13, "#ffb8c8", rot=s_ * 22, ombre=0, contour=False),
                      pivot=(x - 45 * s_, 250), parent="tete", z=6)
    corps = pieds(beige)
    corps += forme("M210,470 Q300,430 390,470 L420,660 Q300,700 180,660 Z", robe)
    corps += trait("M200,640 Q300,690 400,640", "#ffffff", 6, 'stroke-dasharray="2 18"')
    corps += forme("M215,445 Q300,500 385,445 L392,480 Q300,535 208,480 Z", "#9b59d0")
    corps += forme("M330,480 L365,575 L330,570 Z", "#9b59d0", reflet=0)
    p["corps"] = dict(svg=corps, pivot=(300, 690), parent=None, z=3)
    p["bras_g"] = dict(svg=bras(222, 480, 160, 590, poil, beige), pivot=(222, 480), parent="corps", z=4)
    p["bras_d"] = dict(svg=bras(378, 480, 440, 590, poil, beige), pivot=(378, 480), parent="corps", z=4)
    tete = ""
    tete += forme("M228,165 Q198,95 232,52 Q236,108 260,158 Z", corne)
    tete += forme("M372,165 Q402,95 368,52 Q364,108 340,158 Z", corne)
    tete += forme("M300,130 C430,130 455,250 430,330 C410,410 360,440 300,440 C240,440 190,410 170,330 C145,250 170,130 300,130 Z", poil)
    tete += forme("M280,430 Q300,500 320,430 Z", beige)
    tete += ell(300, 345, 70, 48, beige, reflet=0.2)
    tete += plein(ell_d(285, 330, 7, 10), "#7a4b52") + plein(ell_d(315, 330, 7, 10), "#7a4b52")
    tete += forme("M265,150 Q300,120 335,150 Q320,175 300,165 Q280,175 265,150 Z", beige, reflet=0)
    tete += joues(200, 400, 320, 24)
    p["tete"] = dict(svg=tete, pivot=(300, 430), parent="corps", z=5)
    p["yeux_ouverts"] = dict(svg=yeux_ouverts(245, 355, 255, 32, 38), pivot=(300, 430), parent="tete", z=7)
    p["yeux_fermes"] = dict(svg=yeux_fermes(245, 355, 258, 32), pivot=(300, 430), parent="tete", z=7)
    lun = ""
    for x in (245, 355):
        lun += f'<circle cx="{x}" cy="255" r="50" fill="#bfe8ff" fill-opacity="0.28" stroke="#ff4f8b" stroke-width="9"/>'
    lun += trait("M295,250 Q300,240 305,250", "#ff4f8b", 8)
    p["lunettes"] = dict(svg=lun, pivot=(300, 430), parent="tete", z=8)
    p["bouche_fermee"] = dict(svg=bouche_fermee(300, 372, 26), pivot=(300, 430), parent="tete", z=7)
    p["bouche_ouverte"] = dict(svg=bouche_ouverte(300, 368, 28, 36), pivot=(300, 430), parent="tete", z=7)
    return p


def hibou():
    brun, creme, jaune = "#c4793c", "#ffe2b5", "#ffd23f"
    p = {}
    for nom, x, s_ in (("oreille_g", 200, -1), ("oreille_d", 400, 1)):
        d = f"M{x - 35 * s_},{175} L{x + 5 * s_},{80} L{x + 45 * s_},{165} Z"
        p[nom] = dict(svg=forme(d, "#a35e2c"), pivot=(x + 5 * s_, 170), parent="tete", z=1)
    corps = pieds("#ff9a1f", ry=20)
    corps += ell(300, 540, 140, 150, brun)
    corps += ell(300, 565, 95, 110, creme, reflet=0.1)
    for k, y in enumerate((520, 560, 600, 640)):
        for x in range(255 - 10 * (k % 2), 350, 30):
            corps += trait(f"M{x - 10},{y} Q{x},{y + 12} {x + 10},{y}", "#d9a066", 5)
    p["corps"] = dict(svg=corps, pivot=(300, 690), parent=None, z=3)
    for nom, s_ in (("bras_g", -1), ("bras_d", 1)):
        x = 300 + 135 * s_
        d = f"M{x - 25 * s_},450 Q{x + 45 * s_},500 {x + 25 * s_},620 Q{x - 5 * s_},600 {x - 30 * s_},520 Z"
        p[nom] = dict(svg=forme(d, "#a35e2c"), pivot=(x - 20 * s_, 460), parent="corps", z=4)
    tete = ell(300, 290, 165, 145, brun)
    tete += forme("M300,340 L282,305 L318,305 Z", "#ff9a1f", reflet=0.3)
    p["tete"] = dict(svg=tete, pivot=(300, 430), parent="corps", z=5)
    p["yeux_ouverts"] = dict(svg=yeux_ouverts(232, 368, 270, 42, 46, anneau=jaune), pivot=(300, 430), parent="tete", z=6)
    p["yeux_fermes"] = dict(svg=ell(232, 270, 60, 62, jaune) + ell(368, 270, 60, 62, jaune) + yeux_fermes(232, 368, 272, 42),
                            pivot=(300, 430), parent="tete", z=6)
    noeud = forme("M300,440 L250,415 L250,465 Z", "#3cb371") + forme("M300,440 L350,415 L350,465 Z", "#3cb371") + ell(300, 440, 14, 14, "#2e9b5c")
    p["noeud"] = dict(svg=noeud, pivot=(300, 430), parent="corps", z=7)
    p["bouche_fermee"] = dict(svg=trait("M286,358 Q300,368 314,358", ep=6), pivot=(300, 430), parent="tete", z=6)
    p["bouche_ouverte"] = dict(svg=forme("M282,350 Q300,395 318,350 Z", "#8c1d3a", ombre=0, reflet=0, ep=6),
                               pivot=(300, 430), parent="tete", z=6)
    return p


def croco():
    vert, clair, fonce = "#5dbb4f", "#cdeb8b", "#3f9a3a"
    p = {}
    p["queue"] = dict(svg=forme("M390,620 Q500,640 560,560 Q520,610 400,580 Z", vert), pivot=(395, 600), parent="corps", z=0)
    corps = pieds(fonce, rx=50)
    corps += ell(300, 545, 125, 135, vert)
    corps += ell(300, 570, 80, 100, clair, reflet=0.15)
    for y in (520, 560, 600, 640):
        corps += trait(f"M{245},{y} Q300,{y + 10} {355},{y}", "#a9cf6a", 5)
    p["corps"] = dict(svg=corps, pivot=(300, 690), parent=None, z=3)
    p["bras_g"] = dict(svg=bras(200, 480, 145, 585, vert, fonce), pivot=(200, 480), parent="corps", z=4)
    p["bras_d"] = dict(svg=bras(400, 480, 455, 585, vert, fonce), pivot=(400, 480), parent="corps", z=4)
    tete = ell(240, 175, 48, 48, vert) + ell(360, 175, 48, 48, vert)
    tete += forme("M150,280 C150,190 450,190 450,280 L455,360 C455,430 145,430 145,360 Z", vert)
    tete += plein(ell_d(270, 300, 8, 6), fonce) + plein(ell_d(330, 300, 8, 6), fonce)
    for x, y in ((200, 250), (390, 240), (230, 390), (380, 380)):
        tete += plein(ell_d(x, y, 10, 7), fonce, 0.6)
    tete += joues(190, 410, 340, 26)
    p["tete"] = dict(svg=tete, pivot=(300, 425), parent="corps", z=5)
    p["yeux_ouverts"] = dict(svg=yeux_ouverts(240, 360, 168, 30, 34), pivot=(300, 425), parent="tete", z=6)
    p["yeux_fermes"] = dict(svg=yeux_fermes(240, 360, 172, 30), pivot=(300, 425), parent="tete", z=6)
    dents = "".join(forme(f"M{x - 9},{y} L{x + 9},{y} L{x},{y + 16} Z", "#ffffff", ombre=0, reflet=0, ep=4)
                    for x, y in ((235, 343), (265, 349), (335, 349), (365, 343)))
    p["bouche_fermee"] = dict(svg=trait("M205,335 Q300,375 395,335", ep=8) + dents, pivot=(300, 425), parent="tete", z=6)
    p["bouche_ouverte"] = dict(svg=forme("M205,335 Q300,365 395,335 Q380,415 300,418 Q220,415 205,335 Z", "#8c1d3a", ombre=0, reflet=0)
                               + plein(ell_d(300, 395, 50, 16), "#ff7f9b") + dents, pivot=(300, 425), parent="tete", z=6)
    chapeau = forme("M215,140 L385,140 L380,95 L220,95 Z", "#ffffff", ombre=0.08)
    chapeau += forme("M225,100 C170,60 210,0 260,25 C280,-15 330,-10 345,25 C395,5 430,60 375,100 Z", "#ffffff", ombre=0.1)
    noeud = forme("M300,445 L245,420 L245,470 Z", "#ff4f5e") + forme("M300,445 L355,420 L355,470 Z", "#ff4f5e") + ell(300, 445, 14, 14, "#d93445")
    p["chapeau"] = dict(svg=chapeau, pivot=(300, 425), parent="tete", z=7)
    p["noeud"] = dict(svg=noeud, pivot=(300, 425), parent="corps", z=7)
    return p


PERSONNAGES = {"lapin": lapin, "cochon": cochon, "biquette": biquette, "hibou": hibou, "croco": croco}


# ===================================================================== accessoires
def gateau():
    s = forme("M60,330 L540,330 Q560,350 540,370 L60,370 Q40,350 60,330 Z", "#ffffff")
    s += forme("M110,200 L490,200 L500,330 L100,330 Z", "#ff9cc2")
    s += forme("M100,200 Q150,240 200,200 Q250,240 300,200 Q350,240 400,200 Q450,240 500,200 L490,180 L110,180 Z", "#fff6ec", ombre=0.05)
    s += forme("M160,110 L440,110 L450,190 L150,190 Z", "#ffd84d")
    s += forme("M150,110 Q200,140 250,110 Q300,140 350,110 Q400,140 450,110 L440,95 L160,95 Z", "#fff6ec", ombre=0.05)
    for x in (190, 300, 410):
        s += ell(x, 90, 20, 20, "#e8233f", reflet=0.45)
    s += forme("M292,20 L308,20 L308,80 L292,80 Z", "#7fd8ff", ombre=0, ep=5)
    s += ell(300, 5, 12, 18, "#ffb020", ombre=0, ep=4)
    return svg(s, 600, 400)


def parapluie(couleur):
    s = forme("M40,170 Q300,-60 560,170 Q495,140 430,170 Q365,140 300,170 Q235,140 170,170 Q105,140 40,170 Z", couleur)
    s += trait("M300,165 L300,420 Q300,460 260,450", CONTOUR, 16) + trait("M300,165 L300,420 Q300,460 260,450", "#8b5a2b", 8)
    return svg(s, 600, 480)


def oiseau(ailes_hautes):
    s = ell(150, 120, 70, 55, "#4fb3ff")
    s += forme("M210,110 L255,120 L210,135 Z", "#ffa12b", reflet=0)
    if ailes_hautes:
        s += forme("M120,100 Q100,20 170,40 Q170,80 150,105 Z", "#2d8fe0")
    else:
        s += forme("M120,120 Q90,190 165,175 Q165,140 150,120 Z", "#2d8fe0")
    s += ell(175, 105, 9, 10, "#2b1a2e", ombre=0, reflet=0, contour=False) + plein(ell_d(172, 101, 3, 3), "#fff")
    s += plein(ell_d(185, 130, 10, 6), "#ff8fb0", 0.7)
    return svg(s, 300, 220)


ACCESSOIRES = {"gateau": gateau, "parapluie_jaune": lambda: parapluie("#ffd23f"),
               "parapluie_rose": lambda: parapluie("#ff6fa5"),
               "oiseau_a": lambda: oiseau(True), "oiseau_b": lambda: oiseau(False)}

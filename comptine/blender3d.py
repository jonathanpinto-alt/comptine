"""Modélisation et rendu 3D (Blender, moteur Eevee) — exécuté DANS Blender.

    blender -b -P comptine/blender3d.py -- <dossier_sortie> <quoi> [qualite]

`quoi` : persos | decors | sprites | test:<nom>

Tout est construit par code à partir de primitives (sphères, métaballes,
courbes) avec des matériaux doux et brillants, un éclairage studio (lumière
principale, contre-jour, ambiance de ciel) 
pour obtenir un rendu « dessin animé 3D » façon série pour enfants.

Les personnages sont rendus sur fond transparent (sprites 3D) dans plusieurs
états (normal, yeux fermés, bouche ouverte) ; les décors en 1920x1080, le ciel
transparent pour garder un dégradé animé derrière.
"""
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

D2R = math.pi / 180


# =====================================================================  outils
def hexa(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    # sRGB -> linéaire
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*c, a)


_MATS = {}


def mat(nom, couleur, rough=0.45, sss=0.0, coat=0.0, emission=0.0, metal=0.0, spec=0.5):
    cle = (nom, couleur, rough, sss, coat, emission)
    if cle in _MATS:
        return _MATS[cle]
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexa(couleur)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (0.3, 0.15, 0.1)
        b.inputs["Subsurface Scale"].default_value = 0.08
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.15
    if emission:
        b.inputs["Emission Color"].default_value = hexa(couleur)
        b.inputs["Emission Strength"].default_value = emission
    _MATS[cle] = m
    return m


def lisser(obj, niveaux=0):
    for p in obj.data.polygons:
        p.use_smooth = True
    if niveaux:
        mod = obj.modifiers.new("subdiv", "SUBSURF")
        mod.levels = niveaux
        mod.render_levels = niveaux


def sphere(nom, loc, taille, materiau, rot=(0, 0, 0), seg=48, parent=None):
    """Ellipsoïde : taille = (rx, ry, rz)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=1, location=loc)
    o = bpy.context.object
    o.name = nom
    o.scale = taille if isinstance(taille, (tuple, list)) else (taille,) * 3
    o.rotation_euler = [r * D2R for r in rot]
    lisser(o)
    o.data.materials.append(materiau)
    if parent:
        o.parent = parent
    return o


def cone(nom, loc, r1, r2, h, materiau, rot=(0, 0, 0), biseau=0.0):
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=r1, radius2=r2, depth=h, location=loc)
    o = bpy.context.object
    o.name = nom
    o.rotation_euler = [r * D2R for r in rot]
    if biseau:
        mod = o.modifiers.new("biseau", "BEVEL")
        mod.width = biseau
        mod.segments = 6
    lisser(o)
    o.data.materials.append(materiau)
    return o


def cylindre(nom, loc, r, h, materiau, rot=(0, 0, 0), biseau=0.0, sommets=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=sommets, radius=r, depth=h, location=loc)
    o = bpy.context.object
    o.name = nom
    o.rotation_euler = [x * D2R for x in rot]
    if biseau:
        mod = o.modifiers.new("biseau", "BEVEL")
        mod.width = biseau
        mod.segments = 8
        mod.limit_method = "NONE"
    lisser(o)
    o.data.materials.append(materiau)
    return o


def boite(nom, loc, dims, materiau, rot=(0, 0, 0), biseau=0.05):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = nom
    o.scale = dims
    o.rotation_euler = [x * D2R for x in rot]
    bpy.ops.object.transform_apply(scale=True)
    if biseau:
        mod = o.modifiers.new("biseau", "BEVEL")
        mod.width = biseau
        mod.segments = 6
    lisser(o)
    o.data.materials.append(materiau)
    return o


def metaballes(nom, elements, materiau, resolution=0.04):
    """elements : [(type, (x,y,z), rayon, (sx,sy,sz), rot_euler_deg)] fusionnés en douceur."""
    mb = bpy.data.metaballs.new(nom)
    mb.resolution = resolution
    mb.render_resolution = resolution
    mb.threshold = 0.6
    for typ, co, r, taille, rot in elements:
        e = mb.elements.new(type=typ)
        e.co = co
        e.radius = r
        if typ == "ELLIPSOID":
            e.size_x, e.size_y, e.size_z = taille
        elif typ == "CAPSULE":
            e.size_x = taille[0]
        from mathutils import Euler
        e.rotation = Euler([x * D2R for x in rot]).to_quaternion()
    o = bpy.data.objects.new(nom, mb)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(materiau)
    return o


def tube(nom, points, rayon, materiau, fermer=False):
    """Courbe épaisse (sourire, queue en tire-bouchon…)."""
    cu = bpy.data.curves.new(nom, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = rayon
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for p, co in zip(sp.points, points):
        p.co = (*co, 1)
    sp.use_endpoint_u = True
    sp.order_u = min(4, len(points))
    sp.use_cyclic_u = fermer
    o = bpy.data.objects.new(nom, cu)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(materiau)
    return o


# ===================================================================== visage
NOIR = "#2a1a1a"


def oeil(x, y, z, r0, etat, regard=(0, 0), couleur_iris="#5a3418", peau="#ffffff", inclinaison=0):
    """Gros oeil brillant façon dessin animé 3D. (x, y, z) : centre, face vers -Y."""
    r = r0 * 1.22
    if etat == "cligne":
        # paupière fermée : arc sombre + petit bombé de peau
        sphere("paupiere", (x, y + r * 0.35, z), (r * 0.95, r * 0.45, r * 0.9), mat("peau_oeil", peau, 0.5, 0.1))
        pts = [(x - r * 0.75, y - r * 0.12, z + r * 0.05), (x - r * 0.35, y - r * 0.2, z - r * 0.25),
               (x + r * 0.35, y - r * 0.2, z - r * 0.25), (x + r * 0.75, y - r * 0.12, z + r * 0.05)]
        tube("cil", pts, r * 0.09, mat("trait", NOIR, 0.4))
        return
    blanc = mat("blanc_oeil", "#ffffff", 0.12, coat=0.6)
    sphere("sclere", (x, y, z), (r * 0.82, r * 0.5, r), blanc, rot=(0, inclinaison, 0))
    gx, gz = regard
    iris = mat("iris_" + couleur_iris, couleur_iris, 0.15, coat=0.8)
    sphere("iris", (x + gx * r * 0.15, y - r * 0.38, z - r * 0.08 + gz * r * 0.1), (r * 0.6, r * 0.22, r * 0.68), iris)
    sphere("pupille", (x + gx * r * 0.15, y - r * 0.52, z - r * 0.05 + gz * r * 0.1), (r * 0.36, r * 0.12, r * 0.42),
           mat("pupille", "#120808", 0.1, coat=1.0))
    reflet = mat("reflet", "#ffffff", 0.2, emission=6.0)
    sphere("reflet1", (x + r * 0.2, y - r * 0.66, z + r * 0.25), (r * 0.17, r * 0.06, r * 0.2), reflet)
    sphere("reflet2", (x - r * 0.18, y - r * 0.62, z - r * 0.3), (r * 0.08, r * 0.04, r * 0.08), reflet)


def bouche(x, y, z, l, etat, profondeur=0.05):
    """Sourire (courbe) ou bouche ouverte (cavité + langue). Face vers -Y."""
    if etat == "chante":
        sphere("bouche", (x, y, z - l * 0.3), (l * 0.8, profondeur + 0.04, l * 0.85), mat("bouche", "#6e1424", 0.5))
        sphere("langue", (x, y - 0.015, z - l * 0.75), (l * 0.55, profondeur + 0.02, l * 0.3), mat("langue", "#ff6f8e", 0.4, 0.2))
        return
    pts = [(x - l, y, z + l * 0.15), (x - l * 0.5, y - 0.01, z - l * 0.35), (x + l * 0.5, y - 0.01, z - l * 0.35),
           (x + l, y, z + l * 0.15)]
    tube("sourire", pts, l * 0.09, mat("trait", NOIR, 0.4))


def joues(x, y, z, r, couleur="#ff8fb1"):
    m = mat("joue_" + couleur, couleur, 0.6)
    for s in (-1, 1):
        sphere("joue", (s * x, y, z), (r, r * 0.25, r * 0.7), m)


# ===================================================================== animaux
# Tous les animaux sont posés au sol (z = 0), regardent vers -Y (la caméra).

def surface(centre, rayons, x, z, dedans=0.0):
    """Point (x, y, z) de la face avant d'un ellipsoïde ; `dedans` l'enfonce vers le centre."""
    cx, cy, cz = centre
    rx, ry, rz = rayons
    u = 1 - ((x - cx) / rx) ** 2 - ((z - cz) / rz) ** 2
    y = cy - ry * math.sqrt(max(u, 0.0))
    return (x, y + dedans, z)


def tete_et_visage(centre, rayons, peau, e, oeil_x, oeil_z, oeil_r, bouche_z, bouche_l, joue_x, joue_z,
                   iris="#5a3418", joue_c="#ff8fb1", sans_bouche=False):
    sphere("tete", centre, rayons, peau)
    for s_ in (-1, 1):
        x, y, z = surface(centre, rayons, s_ * oeil_x, oeil_z)
        oeil(x, y + oeil_r * 0.22, z, oeil_r, e, couleur_iris=iris, peau=peau_hex(peau))
        x, y, z = surface(centre, rayons, s_ * joue_x, joue_z)
        sphere("joue", (x, y + 0.03, z), (oeil_r * 0.6, 0.06, oeil_r * 0.42), mat("joue_" + joue_c, joue_c, 0.6))
    if not sans_bouche:
        x, y, z = surface(centre, rayons, 0, bouche_z)
        bouche(0, y + 0.01, z, bouche_l, e)


def peau_hex(m):
    c = m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value
    f = [x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055 for x in c[:3]]
    return "#%02x%02x%02x" % tuple(int(max(0, min(1, v)) * 255) for v in f)


def pattes(xs, ys, h, r, peau, sabot=None):
    for x in xs:
        for y in ys:
            cylindre("patte", (x, y, h / 2), r, h, peau, biseau=r * 0.4)
            if sabot:
                cylindre("sabot", (x, y, 0.05), r * 1.04, 0.1, sabot, biseau=0.03)


def cochon(e):
    rose = mat("rose", "#ff9ec0", 0.42, sss=0.3)
    rose_f = mat("rose_fonce", "#ff6f9c", 0.42, sss=0.25)
    sphere("corps", (0, 0.2, 0.72), (0.66, 0.62, 0.52), rose)
    pattes((-0.32, 0.32), (-0.08, 0.45), 0.42, 0.15, rose, rose_f)
    T, R = (0, -0.05, 1.62), (0.86, 0.8, 0.8)
    tete_et_visage(T, R, rose, e, 0.33, 1.86, 0.2, 1.17, 0.16, 0.55, 1.45, joue_c="#ff5c8d")
    # groin
    x, y, z = surface(T, R, 0, 1.45)
    cylindre("groin", (0, y - 0.06, z), 0.3, 0.24, rose_f, rot=(90, 0, 0), biseau=0.09)
    narine = mat("narine", "#a8335a", 0.6)
    for nx in (-0.11, 0.11):
        sphere("narine", (nx, y - 0.18, z + 0.01), (0.055, 0.03, 0.09), narine)
    # oreilles souples
    for s_ in (-1, 1):
        sphere("oreille", (s_ * 0.52, -0.05, 2.32), (0.2, 0.07, 0.3), rose_f, rot=(-25, s_ * -35, 0))
    tube("queue", [(0, 0.8, 0.85), (0.12, 0.95, 0.95), (-0.04, 1.02, 1.05), (0.1, 0.95, 1.15)], 0.04, rose)


def vache(e):
    blanc = mat("blanc_vache", "#fbf7f2", 0.48, sss=0.2)
    tache = mat("tache", "#4a2e25", 0.5)
    rose = mat("museau", "#ffadc4", 0.42, sss=0.25)
    C_, Rc = (0, 0.25, 0.85), (0.7, 0.62, 0.55)
    sphere("corps", C_, Rc, blanc)
    pattes((-0.36, 0.36), (-0.02, 0.55), 0.5, 0.16, blanc, tache)
    for x, z, r in ((0.42, 0.95, 0.22), (-0.38, 0.7, 0.2)):
        px, py, pz = surface(C_, Rc, x, z)
        sphere("tache", (px, py + 0.08, pz), (r, 0.12, r * 0.85), tache)
    T, R = (0, -0.05, 1.82), (0.92, 0.82, 0.84)
    tete_et_visage(T, R, blanc, e, 0.34, 2.02, 0.21, 1.3, 0.17, 0.62, 1.62, sans_bouche=True)
    px, py, pz = surface(T, R, 0.45, 2.38)
    sphere("tache_tete", (px, py + 0.1, pz), (0.24, 0.12, 0.2), tache)
    # gros museau rose avec bouche
    mx, my, mz = surface(T, R, 0, 1.42)
    M, Rm = (0, my + 0.12, mz), (0.56, 0.33, 0.34)
    sphere("museau", M, Rm, rose)
    narine = mat("narine_v", "#c0587a", 0.6)
    for nx in (-0.19, 0.19):
        x, y, z = surface(M, Rm, nx, mz + 0.08)
        sphere("narine", (x, y + 0.01, z), (0.06, 0.03, 0.08), narine)
    x, y, z = surface(M, Rm, 0, mz - 0.17)
    bouche(0, y + 0.01, z, 0.16, e)
    corne = mat("corne", "#ffe08a", 0.3, coat=0.3)
    for s_ in (-1, 1):
        cone("corne", (s_ * 0.42, -0.05, 2.68), 0.1, 0.05, 0.3, corne, rot=(0, s_ * -22, 0), biseau=0.04)
        sphere("oreille", (s_ * 0.9, -0.05, 2.2), (0.34, 0.1, 0.16), blanc, rot=(0, s_ * -18, 0))
        sphere("oreille_in", (s_ * 0.9, -0.12, 2.2), (0.25, 0.05, 0.1), rose, rot=(0, s_ * -18, 0))
    tube("queue", [(0.25, 0.85, 1.0), (0.35, 1.0, 0.8), (0.38, 1.05, 0.55)], 0.035, blanc)
    sphere("pompon", (0.38, 1.05, 0.5), 0.08, tache)


def coq(e):
    blanc = mat("plume_blanche", "#fffaf3", 0.55, sss=0.15)
    rouge = mat("crete", "#f2353b", 0.38, sss=0.25)
    jaune = mat("bec", "#ffb000", 0.3, coat=0.4)
    sphere("corps", (0, 0.15, 0.85), (0.62, 0.58, 0.6), blanc)
    for x in (-0.18, 0.18):
        cylindre("patte", (x, 0.1, 0.18), 0.05, 0.36, jaune)
        for a in (-30, 0, 30):
            cylindre("doigt", (x + 0.08 * math.sin(a * D2R), 0.02 - 0.08 * math.cos(a * D2R), 0.03), 0.032, 0.2,
                     jaune, rot=(90, 0, a))
    for k, c in enumerate(["#2e9e5b", "#2c6fd6", "#e53935", "#ffb300"]):
        a = -40 + k * 25
        sphere("queue", (0.1 + 0.15 * math.sin(a * D2R), 0.7, 1.25 + 0.06 * k), (0.15, 0.12, 0.52),
               mat("queue" + c, c, 0.32, coat=0.4), rot=(-25, a, 0))
    for s_ in (-1, 1):
        sphere("aile", (s_ * 0.6, 0.15, 0.85), (0.14, 0.4, 0.34), blanc, rot=(0, s_ * 15, 0))
    T, R = (0, -0.02, 1.68), (0.66, 0.62, 0.64)
    tete_et_visage(T, R, blanc, e, 0.25, 1.82, 0.17, 0, 0, 0.45, 1.55, sans_bouche=True)
    for x, z, r in ((-0.17, 2.3, 0.15), (0.02, 2.38, 0.18), (0.2, 2.3, 0.15)):
        sphere("crete", (x, -0.05, z), r, rouge)
    x, y, z = surface(T, R, 0, 1.55)
    if e == "chante":
        cone("bec_haut", (0, y - 0.12, z + 0.06), 0.14, 0.0, 0.32, jaune, rot=(-78, 0, 0), biseau=0.02)
        cone("bec_bas", (0, y - 0.07, z - 0.1), 0.11, 0.0, 0.24, jaune, rot=(-112, 0, 0), biseau=0.02)
        sphere("gorge", (0, y - 0.02, z - 0.02), (0.09, 0.05, 0.07), mat("bouche", "#6e1424", 0.5))
    else:
        cone("bec", (0, y - 0.12, z), 0.14, 0.0, 0.32, jaune, rot=(-90, 0, 0), biseau=0.02)
    sphere("barbillon", (0, y + 0.02, z - 0.25), (0.11, 0.07, 0.16), rouge)


def canard(e):
    jaune = mat("plume_jaune", "#ffdd33", 0.5, sss=0.15)
    orange = mat("bec_orange", "#ff8f00", 0.3, coat=0.4)
    sphere("corps", (0, 0.25, 0.62), (0.72, 0.75, 0.52), jaune)
    sphere("croupion", (0, 0.95, 0.85), (0.28, 0.35, 0.22), jaune, rot=(-35, 0, 0))
    for s_ in (-1, 1):
        sphere("aile", (s_ * 0.68, 0.3, 0.7), (0.15, 0.45, 0.3), jaune, rot=(0, s_ * 12, 0))
        sphere("pied", (s_ * 0.24, -0.25, 0.05), (0.18, 0.24, 0.05), orange)
    T, R = (0, -0.12, 1.5), (0.72, 0.68, 0.7)
    tete_et_visage(T, R, jaune, e, 0.27, 1.7, 0.19, 0, 0, 0.5, 1.4, sans_bouche=True)
    sphere("houppe", (0.0, -0.12, 2.22), (0.08, 0.06, 0.16), jaune, rot=(0, 20, 0))
    sphere("houppe2", (0.1, -0.12, 2.19), (0.07, 0.05, 0.13), jaune, rot=(0, 50, 0))
    x, y, z = surface(T, R, 0, 1.35)
    if e == "chante":
        sphere("bec_haut", (0, y - 0.14, z + 0.06), (0.32, 0.22, 0.08), orange, rot=(-14, 0, 0))
        sphere("bec_bas", (0, y - 0.09, z - 0.13), (0.26, 0.17, 0.07), orange, rot=(16, 0, 0))
        sphere("gorge", (0, y - 0.07, z - 0.03), (0.2, 0.09, 0.08), mat("bouche", "#6e1424", 0.5))
    else:
        sphere("bec", (0, y - 0.15, z), (0.33, 0.24, 0.1), orange)
        tube("fente", [(-0.29, y - 0.2, z), (0, y - 0.38, z - 0.01), (0.29, y - 0.2, z)], 0.012,
             mat("trait_b", "#c06000", 0.4))


def mouton(e):
    laine = mat("laine", "#ffffff", 0.9, sss=0.15)
    visage = mat("visage_mouton", "#6e6280", 0.5, sss=0.2)
    pattes((-0.3, 0.3), (0.0, 0.5), 0.45, 0.09, visage)
    sphere("corps", (0, 0.3, 0.88), (0.62, 0.55, 0.48), laine)
    for k in range(14):
        a = k / 14 * 2 * math.pi
        sphere("boucle", (0.62 * math.cos(a), 0.3 + 0.35 * math.sin(a), 0.88 + 0.32 * math.sin(a * 2 + 1) * 0.5),
               0.3 + 0.05 * math.sin(k * 1.7), laine, seg=32)
    for k in range(7):
        a = k / 7 * 2 * math.pi
        sphere("boucle_haut", (0.45 * math.cos(a), 0.3 + 0.3 * math.sin(a), 1.25), 0.27, laine, seg=32)
    T, R = (0, -0.35, 1.62), (0.52, 0.45, 0.6)
    tete_et_visage(T, R, visage, e, 0.21, 1.72, 0.17, 1.3, 0.11, 0.37, 1.45)
    for x, z in [(-0.28, 2.15), (0, 2.25), (0.28, 2.15), (-0.14, 2.1), (0.14, 2.1)]:
        sphere("frange", (x, -0.3, z), 0.2, laine, seg=32)
    for s_ in (-1, 1):
        sphere("oreille", (s_ * 0.6, -0.25, 1.85), (0.28, 0.1, 0.12), visage, rot=(0, s_ * 25, 0))


def cheval(e):
    brun = mat("robe", "#c8834d", 0.48, sss=0.2)
    creme = mat("creme", "#f5d2a8", 0.48, sss=0.2)
    criniere = mat("criniere", "#6b3b22", 0.6)
    sphere("corps", (0, 0.35, 1.0), (0.6, 0.75, 0.5), brun)
    pattes((-0.3, 0.3), (0.0, 0.72), 0.75, 0.13, brun, criniere)
    T, R = (0, -0.15, 1.95), (0.68, 0.62, 0.74)
    tete_et_visage(T, R, brun, e, 0.3, 2.15, 0.2, 0, 0, 0.5, 1.8, sans_bouche=True)
    x, y, z = surface(T, R, 0, 1.58)
    M, Rm = (0, y + 0.1, z), (0.5, 0.36, 0.36)
    sphere("museau", M, Rm, creme)
    narine = mat("narine_c", "#8a5a3a", 0.6)
    for nx in (-0.17, 0.17):
        x, y, z = surface(M, Rm, nx, M[2] + 0.1)
        sphere("narine", (x, y + 0.01, z), (0.055, 0.03, 0.08), narine)
    x, y, z = surface(M, Rm, 0, M[2] - 0.15)
    bouche(0, y + 0.01, z, 0.15, e)
    for s_ in (-1, 1):
        sphere("oreille", (s_ * 0.33, -0.12, 2.72), (0.11, 0.07, 0.24), brun, rot=(0, s_ * -15, 0))
    for x, y, z, r in [(0, -0.38, 2.68, 0.2), (0.08, -0.1, 2.72, 0.22), (0.12, 0.2, 2.55, 0.2),
                       (0.1, 0.45, 2.25, 0.18), (0.05, 0.65, 1.9, 0.16)]:
        sphere("criniere", (x, y, z), r, criniere)
    tube("queue", [(0, 1.05, 1.2), (0.05, 1.3, 1.05), (0.1, 1.4, 0.65)], 0.11, criniere)


def poussin(e):
    jaune = mat("duvet", "#ffe838", 0.6, sss=0.2)
    orange = mat("bec_p", "#ff8f00", 0.3, coat=0.4)
    C_, Rc = (0, 0, 0.74), (0.74, 0.7, 0.72)
    sphere("corps", C_, Rc, jaune)
    for s_ in (-1, 1):
        sphere("aile", (s_ * 0.7, 0.05, 0.72), (0.12, 0.28, 0.3), jaune, rot=(0, s_ * 25, 0))
        cylindre("patte", (s_ * 0.18, -0.05, 0.05), 0.04, 0.12, orange)
        sphere("pied", (s_ * 0.18, -0.2, 0.02), (0.1, 0.14, 0.03), orange)
    sphere("houppe", (0, -0.05, 1.5), (0.07, 0.05, 0.15), jaune, rot=(0, -15, 0))
    sphere("houppe2", (0.08, -0.05, 1.48), (0.06, 0.04, 0.12), jaune, rot=(0, 30, 0))
    for s_ in (-1, 1):
        x, y, z = surface(C_, Rc, s_ * 0.26, 0.95)
        oeil(x, y + 0.04, z, 0.18, e, peau="#ffe838")
        x, y, z = surface(C_, Rc, s_ * 0.45, 0.68)
        sphere("joue", (x, y + 0.03, z), (0.1, 0.05, 0.07), mat("joue_p", "#ff8fb1", 0.6))
    x, y, z = surface(C_, Rc, 0, 0.66)
    if e == "chante":
        cone("bec_haut", (0, y - 0.07, z + 0.05), 0.1, 0.0, 0.22, orange, rot=(-72, 0, 0), biseau=0.02)
        cone("bec_bas", (0, y - 0.05, z - 0.07), 0.08, 0.0, 0.16, orange, rot=(-115, 0, 0), biseau=0.02)
        sphere("gorge", (0, y - 0.01, z - 0.01), (0.06, 0.03, 0.05), mat("bouche", "#6e1424", 0.5))
    else:
        cone("bec", (0, y - 0.08, z), 0.1, 0.0, 0.22, orange, rot=(-90, 0, 0), biseau=0.02)


ANIMAUX = {"cochon": cochon, "vache": vache, "coq": coq, "canard": canard, "mouton": mouton,
           "cheval": cheval, "poussin": poussin}
ETATS = ("normal", "cligne", "chante")


# ===================================================================== scène
def vider():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()


def reglages(largeur, hauteur, echantillons, transparent=True):
    """Eevee : rendu sans bruit, ombres douces, occlusion ambiante, subsurface, bloom."""
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    ev = sc.eevee
    ev.taa_render_samples = echantillons
    ev.use_gtao = True
    ev.gtao_distance = 0.8
    ev.gtao_factor = 1.0
    ev.use_soft_shadows = True
    ev.shadow_cube_size = "2048"
    ev.shadow_cascade_size = "4096"
    ev.use_shadow_high_bitdepth = True
    ev.use_bloom = not transparent
    ev.bloom_intensity = 0.03
    ev.bloom_threshold = 1.2
    ev.sss_samples = 9
    ev.use_ssr = True
    sc.render.resolution_x = largeur
    sc.render.resolution_y = hauteur
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.filter_size = 1.2
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0


def monde(couleur_haut="#bfe3ff", couleur_bas="#fff4e0", force=0.9):
    w = bpy.data.worlds.new("ciel")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = hexa(couleur_bas)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = hexa(couleur_haut)
    maprange = nt.nodes.new("ShaderNodeMapRange")
    maprange.inputs["From Min"].default_value = -1
    maprange.inputs["From Max"].default_value = 1
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], maprange.inputs["Value"])
    nt.links.new(maprange.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = force


def lumiere_aire(nom, loc, cible, puissance, taille, couleur="#ffffff"):
    d = bpy.data.lights.new(nom, "AREA")
    d.energy = puissance
    d.size = taille
    d.color = hexa(couleur)[:3]
    o = bpy.data.objects.new(nom, d)
    bpy.context.collection.objects.link(o)
    o.location = loc
    direction = Vector(cible) - Vector(loc)
    o.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return o


def soleil_lumiere(rot, force, couleur="#fff3dc", angle=6):
    d = bpy.data.lights.new("soleil", "SUN")
    d.energy = force
    d.angle = angle * D2R
    d.color = hexa(couleur)[:3]
    o = bpy.data.objects.new("soleil", d)
    bpy.context.collection.objects.link(o)
    o.rotation_euler = [r * D2R for r in rot]
    return o


def eclairage_studio(chaud=True):
    # lumière principale douce (haut-gauche-avant), contre-jour (bord lumineux), débouchage
    lumiere_aire("cle", (-4, -6, 6), (0, 0, 1.2), 1700, 4, "#fff0dc" if chaud else "#ffffff")
    lumiere_aire("contre", (3.5, 5, 4.5), (0, 0, 1.4), 1400, 3, "#eaf2ff")
    lumiere_aire("debouche", (5, -5, 2), (0, 0, 1.0), 300, 5, "#ffe9f2")


def camera_ortho(echelle, centre_z, inclinaison=6):
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    cam.ortho_scale = echelle
    o = bpy.data.objects.new("cam", cam)
    bpy.context.collection.objects.link(o)
    d = 20
    a = inclinaison * D2R
    o.location = (0, -d * math.cos(a), centre_z + d * math.sin(a))
    o.rotation_euler = (math.pi / 2 - a, 0, 0)
    bpy.context.scene.camera = o
    return o


def ancre(cam, point=(0, 0, 0)):
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    v = world_to_camera_view(sc, cam, Vector(point))
    return v.x, 1 - v.y


def rendre(chemin):
    bpy.context.scene.render.filepath = str(chemin)
    bpy.ops.render.render(write_still=True)


# ===================================================================== tâches
TAILLE_SPRITE = 900
ECHELLE_ORTHO = 3.4          # mètres visibles en largeur dans un sprite
CENTRE_Z = 1.45


def rendre_persos(sortie, qualite, seulement=None):
    os.makedirs(sortie, exist_ok=True)
    meta = {}
    for nom, f in ANIMAUX.items():
        if seulement and nom not in seulement:
            continue
        for e in ETATS:
            vider()
            reglages(TAILLE_SPRITE, TAILLE_SPRITE, qualite)
            monde("#cfe8ff", "#fff0e6", 0.45)
            eclairage_studio()
            f(e)
            cam = camera_ortho(ECHELLE_ORTHO, CENTRE_Z)
            ax, ay = ancre(cam)
            meta[nom] = {"ancre": [ax, ay], "px_par_m": TAILLE_SPRITE / ECHELLE_ORTHO}
            rendre(os.path.join(sortie, f"{nom}_{e}.png"))
    with open(os.path.join(sortie, "persos.json"), "w") as fh:
        json.dump(meta, fh, indent=1)


# ===================================================================== décors
def sol(couleur, taille=80, relief=0.0, graine=0):
    bpy.ops.mesh.primitive_plane_add(size=taille, location=(0, 0, 0))
    o = bpy.context.object
    o.name = "sol"
    if relief:
        mod = o.modifiers.new("subdiv", "SUBSURF")
        mod.subdivision_type = "SIMPLE"
        mod.levels = mod.render_levels = 6
        tex = bpy.data.textures.new("bosses", "CLOUDS")
        tex.noise_scale = 6
        disp = o.modifiers.new("relief", "DISPLACE")
        disp.texture = tex
        disp.strength = relief
    lisser(o)
    o.data.materials.append(mat("herbe_" + couleur, couleur, 0.8, sss=0.05))
    return o


def colline(x, y, rx, ry, rz, couleur):
    return sphere("colline", (x, y, 0), (rx, ry, rz), mat("colline_" + couleur, couleur, 0.85), seg=64)


def prisme(nom, points_xz, profondeur, loc, materiau, biseau=0.0):
    """Polygone (plan XZ) extrudé selon Y, centré sur loc."""
    import bmesh
    me = bpy.data.meshes.new(nom)
    bm = bmesh.new()
    av = [bm.verts.new((x, -profondeur / 2, z)) for x, z in points_xz]
    ar = [bm.verts.new((x, profondeur / 2, z)) for x, z in points_xz]
    bm.faces.new(av[::-1])
    bm.faces.new(ar)
    n = len(points_xz)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([av[i], av[j], ar[j], ar[i]])
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(nom, me)
    bpy.context.collection.objects.link(o)
    o.location = loc
    if biseau:
        mod = o.modifiers.new("biseau", "BEVEL")
        mod.width = biseau
        mod.segments = 5
        mod.limit_method = "ANGLE"
    me.materials.append(materiau)
    for poly in me.polygons:
        poly.use_smooth = False
    return o


def grange(x, y, s=1.0, nuit=False):
    rouge = mat("grange" + str(nuit), "#e0394f" if not nuit else "#6a2c4a", 0.55)
    toit = mat("toit" + str(nuit), "#8f2638" if not nuit else "#3e1b33", 0.5)
    blanc = mat("bois_blanc" + str(nuit), "#ffffff" if not nuit else "#b9a9d6", 0.5)
    w, d, h, hp = 4.0 * s, 3.0 * s, 2.8 * s, 1.5 * s
    prisme("murs", [(-w / 2, 0), (w / 2, 0), (w / 2, h), (0, h + hp), (-w / 2, h)], d, (x, y, 0), rouge, 0.1 * s)
    # toit : deux pans le long des rampants
    lp = math.hypot(w / 2, hp) + 0.45 * s
    ang = math.degrees(math.atan2(hp, w / 2))
    for sg in (-1, 1):
        boite("pan", (x + sg * w / 4, y, h + hp / 2 + 0.16 * s), (lp, d * 1.12, 0.22 * s), toit,
              rot=(0, sg * ang, 0), biseau=0.08 * s)
    # porte avec cadre et croix blanche
    pw_, ph = 1.6 * s, 1.9 * s
    yf = y - d / 2
    boite("porte", (x, yf - 0.02, ph / 2), (pw_, 0.06, ph), mat("porte" + str(nuit), "#b8293d" if not nuit else "#4f2240", 0.6), biseau=0.02)
    boite("cadre_h", (x, yf - 0.07, ph), (pw_ + 0.2 * s, 0.1, 0.15 * s), blanc, biseau=0.03)
    for sg in (-1, 1):
        boite("cadre_v", (x + sg * pw_ / 2, yf - 0.07, ph / 2), (0.15 * s, 0.1, ph), blanc, biseau=0.03)
    diag = math.degrees(math.atan2(ph, pw_))
    for sg in (-1, 1):
        boite("croix", (x, yf - 0.08, ph / 2), (math.hypot(pw_, ph) * 0.92, 0.08, 0.13 * s), blanc,
              rot=(0, sg * diag, 0), biseau=0.03)
    # bordures blanches des murs
    for sg in (-1, 1):
        boite("angle", (x + sg * (w / 2 - 0.05), yf - 0.04, h / 2), (0.16 * s, 0.1, h), blanc, biseau=0.03)
    # fenêtre ronde du grenier
    zf = h + 0.55 * s
    bpy.ops.mesh.primitive_torus_add(major_radius=0.42 * s, minor_radius=0.08 * s, location=(x, yf - 0.06, zf),
                                     rotation=(math.pi / 2, 0, 0))
    t = bpy.context.object
    lisser(t)
    t.data.materials.append(blanc)
    vitre = mat("vitre" + str(nuit), "#ffd54f" if nuit else "#8fd3ff", 0.1, emission=4.0 if nuit else 0.0)
    cylindre("vitre", (x, yf - 0.02, zf), 0.38 * s, 0.05, vitre, rot=(90, 0, 0))


def arbre(x, y, s=1.0, couleur="#4caf50"):
    tronc = mat("tronc", "#8d5a3b", 0.7)
    feuille = mat("feuillage_" + couleur, couleur, 0.7, sss=0.15)
    cylindre("tronc", (x, y, 1.0 * s), 0.22 * s, 2.0 * s, tronc, biseau=0.05)
    for dx, dz, r in [(-0.55, 2.2, 0.8), (0.55, 2.2, 0.8), (0, 2.85, 0.95), (-0.25, 1.75, 0.65), (0.35, 1.8, 0.65)]:
        sphere("feuilles", (x + dx * s, y, dz * s), r * s, feuille, seg=40)


def sapin(x, y, s=1.0, couleur="#2e7d32"):
    tronc = mat("tronc", "#7b4f33", 0.7)
    vert = mat("sapin_" + couleur, couleur, 0.7, sss=0.1)
    cylindre("tronc", (x, y, 0.3 * s), 0.18 * s, 0.6 * s, tronc)
    for k, (r, h) in enumerate([(1.2, 1.3), (0.95, 1.15), (0.68, 1.0)]):
        cone("etage", (x, y, (0.95 + k * 0.72) * s), r * s, 0.06 * s, h * s, vert, biseau=0.12 * s)


def barriere(x0, x1, y, s=1.0, couleur="#fff8e1"):
    bois = mat("barriere_" + couleur, couleur, 0.55)
    x = x0
    while x <= x1:
        boite("poteau", (x, y, 0.55 * s), (0.18 * s, 0.14 * s, 1.1 * s), bois, biseau=0.06 * s)
        x += 1.0 * s
    for z in (0.75, 0.38):
        boite("lisse", ((x0 + x1) / 2, y - 0.03, z * s), (x1 - x0 + 0.3, 0.1 * s, 0.16 * s), bois, biseau=0.05 * s)


def fleur(x, y, couleur, s=1.0):
    tige = mat("tige", "#43a047", 0.6)
    cylindre("tige", (x, y, 0.2 * s), 0.025 * s, 0.4 * s, tige, sommets=12)
    m = mat("petale_" + couleur, couleur, 0.45, sss=0.2)
    for k in range(5):
        a = k * 2 * math.pi / 5
        sphere("petale", (x + math.cos(a) * 0.1 * s, y - 0.02, 0.42 * s + math.sin(a) * 0.1 * s),
               (0.08 * s, 0.03 * s, 0.08 * s), m, seg=16)
    sphere("coeur", (x, y - 0.05, 0.42 * s), 0.06 * s, mat("coeur_fleur", "#ffd54f", 0.4), seg=16)


def champignon(x, y, s=1.0):
    cylindre("pied", (x, y, 0.22 * s), 0.1 * s, 0.44 * s, mat("pied_ch", "#fff3e0", 0.6), biseau=0.03)
    sphere("chapeau", (x, y, 0.45 * s), (0.36 * s, 0.36 * s, 0.24 * s), mat("chapeau", "#ef3b3b", 0.35, coat=0.4))
    for dx, dz in [(-0.15, 0.58), (0.08, 0.64), (0.2, 0.52)]:
        sphere("pois", (x + dx * s, y - 0.25 * s, dz * s), 0.05 * s, mat("pois", "#ffffff", 0.5), seg=16)


def mare(x, y, rx, ry):
    eau = mat("eau", "#3fb3ff", 0.05, coat=1.0, spec=0.8)
    sphere("bord", (x, y, 0.0), (rx + 0.35, ry + 0.3, 0.12), mat("bord_mare", "#9ccc65", 0.8), seg=64)
    sphere("eau", (x, y, 0.03), (rx, ry, 0.12), eau, seg=64)
    nenu = mat("nenuphar", "#5cb85c", 0.5)
    for dx, dy, r in [(-0.55, -0.1, 0.35), (0.5, 0.3, 0.3), (0.2, -0.45, 0.25)]:
        cylindre("nenuphar", (x + dx * rx, y + dy * ry, 0.15), r, 0.03, nenu)
    sphere("fleur_eau", (x - 0.55 * rx, y - 0.1 * ry, 0.22), 0.1, mat("fleur_eau", "#ff80ab", 0.4))


def roseaux(x, y, n=6):
    tige = mat("roseau", "#558b2f", 0.6)
    epi = mat("epi", "#8d6e63", 0.7)
    for k in range(n):
        h = 1.4 + 0.3 * math.sin(k * 1.7)
        xx = x + k * 0.22
        cylindre("roseau", (xx, y, h / 2), 0.03, h, tige, sommets=12)
        sphere("epi", (xx, y, h), (0.06, 0.06, 0.2), epi, seg=16)


def boue(x, y, rx, ry):
    sphere("boue", (x, y, 0.0), (rx, ry, 0.07), mat("boue", "#7a4a32", 0.35, coat=0.3), seg=64)
    for dx, dy, r in [(-0.3, -0.2, 0.25), (0.35, 0.1, 0.18)]:
        sphere("flaque", (x + dx * rx, y + dy * ry, 0.05), (r, r * 0.6, 0.03), mat("flaque", "#5d3a26", 0.15, coat=0.6), seg=32)


def arc_en_ciel(x, y, r, ep):
    cols = ["#ff5252", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#7e57c2"]
    for k, c in enumerate(cols):
        bpy.ops.mesh.primitive_torus_add(major_radius=r - k * ep * 2, minor_radius=ep, major_segments=96,
                                         minor_segments=16, location=(x, y, 0), rotation=(math.pi / 2, 0, 0))
        t = bpy.context.object
        lisser(t)
        t.data.materials.append(mat("arc_" + c, c, 0.4, emission=0.4))


def camera_decor(lieu=(0, -18, 3.2), cible=(0, 0, 2.2), focale=35):
    cam = bpy.data.cameras.new("cam")
    cam.lens = focale
    o = bpy.data.objects.new("cam", cam)
    bpy.context.collection.objects.link(o)
    o.location = lieu
    o.rotation_euler = (Vector(cible) - Vector(lieu)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = o
    return o


def ambiance(haut, bas, force, soleil_rot, soleil_force, soleil_couleur):
    monde(haut, bas, force)
    soleil_lumiere(soleil_rot, soleil_force, soleil_couleur, angle=10)


FLEURS = ["#ff80ab", "#fff176", "#ce93d8", "#ff8a65", "#80deea", "#ffffff"]


def decor(nom):
    """Construit un décor. Le sol est à z = 0 ; la caméra regarde vers +Y."""
    if nom in ("aube", "pre", "grange", "foret", "fete", "mare"):
        couleurs = {"aube": ("#ffd1c1", "#fff1d6", 3.2, "#ffd9b8"), "foret": ("#d9f0ff", "#fff6dc", 3.6, "#fff0d0")}
        h, b, f, c = couleurs.get(nom, ("#bfe3ff", "#f4fbff", 4.0, "#fff4e0"))
        ambiance(h, b, 0.9, (50, 0, -35), f, c)
    elif nom == "nuit":
        ambiance("#5a4fb0", "#8f78c8", 1.3, (40, 0, 30), 1.6, "#a9bcff")
    elif nom == "couchant":
        ambiance("#ffb3c6", "#ffe0b0", 1.0, (60, 0, 25), 3.4, "#ffc48a")
    nuit = nom == "nuit"
    herbe = {"nuit": "#3d5f8a", "couchant": "#8fbf5a"}.get(nom, "#7cc444")
    herbe2 = {"nuit": "#34507a", "couchant": "#a6c96a"}.get(nom, "#9ad35a")
    sol(herbe, relief=0.25)
    # collines du fond
    for x, yv, rx, rz, c in [(-14, 30, 16, 6, herbe2), (10, 34, 18, 8, herbe2), (0, 45, 30, 12, herbe2),
                             (-25, 40, 14, 9, herbe), (25, 38, 14, 7, herbe)]:
        colline(x, yv, rx, 8, rz, c)
    if nom == "aube":
        grange(-6.5, 10, 1.2)
        barriere(2.5, 12, 3.5, 1.0)
        for k in range(10):
            fleur(-9 + k * 2.1, -4.5 + (k % 2) * 0.8, FLEURS[k % 6], 1.4)
        arbre(-12, 16, 1.4, "#5cb85c")
    elif nom == "pre":
        barriere(-14, 14, 4.0, 1.0)
        arbre(9.5, 12, 1.6, "#5cb85c")
        arbre(13, 16, 1.3, "#81c784")
        arbre(-12, 18, 1.4, "#66bb6a")
        for k in range(14):
            fleur(-11 + k * 1.7, -5 + (k % 3) * 0.9, FLEURS[k % 6], 1.4)
    elif nom == "grange":
        grange(0, 9, 1.6)
        arbre(-9, 13, 1.6, "#5cb85c")
        arbre(9.5, 13, 1.5, "#81c784")
        sapin(-13, 18, 2.2)
        sapin(13.5, 19, 2.0)
        for k in range(10):
            fleur(-10 + k * 2.2, -5 + (k % 2) * 0.8, FLEURS[k % 6], 1.3)
    elif nom == "mare":
        mare(-2.8, -1.5, 4.0, 2.2)
        roseaux(-7.2, -0.5, 6)
        roseaux(1.6, 0.8, 4)
        boue(5.5, -1.0, 2.6, 1.4)
        sapin(-11, 10, 2.0)
        sapin(-8, 13, 1.6, "#388e3c")
        arbre(10, 12, 1.5, "#66bb6a")
        for k in range(5):
            fleur(3 + k * 1.6, -5.5, FLEURS[k], 1.3)
    elif nom == "nuit":
        grange(-6, 11, 1.2, nuit=True)
        sapin(8, 14, 2.0, "#1e3d4f")
        sapin(11, 17, 1.6, "#1b3346")
        arbre(-12, 16, 1.4, "#2a5a5a")
    elif nom == "foret":
        for x, yv, s_, c in [(-11, 8, 1.6, "#43a047"), (-7, 14, 1.9, "#66bb6a"), (8, 9, 1.7, "#4caf50"),
                             (12, 13, 1.5, "#81c784"), (4, 18, 1.8, "#2e7d32"), (-3, 20, 1.6, "#388e3c")]:
            arbre(x, yv, s_, c)
        for x, yv, s_ in [(-4.5, -3, 1.2), (-3.6, -3.4, 0.8), (6, -3.5, 1.0)]:
            champignon(x, yv, s_)
        for k in range(8):
            fleur(-10 + k * 2.8, -5.5 + (k % 2) * 0.7, FLEURS[k % 6], 1.2)
    elif nom == "fete":
        arc_en_ciel(0, 28, 17, 0.75)
        grange(10, 10, 1.1)
        arbre(-11, 12, 1.5, "#5cb85c")
        for k in range(12):
            fleur(-11 + k * 2.0, -5 + (k % 2) * 0.8, FLEURS[k % 6], 1.3)
    elif nom == "couchant":
        grange(9, 11, 1.2)
        arbre(-10, 13, 1.6, "#6d8f4e")
        sapin(-6, 17, 1.8, "#4f6b3a")
    camera_decor()


DECORS = ["aube", "pre", "grange", "mare", "nuit", "foret", "fete", "couchant"]


def rendre_decors(sortie, qualite, seulement=None):
    os.makedirs(sortie, exist_ok=True)
    for nom in DECORS:
        if seulement and nom not in seulement:
            continue
        vider()
        reglages(1920, 1080, qualite, transparent=True)
        bpy.context.scene.eevee.use_bloom = True
        decor(nom)
        rendre(os.path.join(sortie, f"decor_{nom}.png"))


# ===================================================================== accessoires (sprites)
def visage_astre(r, peau, endormi=False):
    if endormi:
        for s_ in (-1, 1):
            tube("oeil_dort", [(s_ * 0.33 * r - 0.12 * r, -r * 0.97, 0.1 * r), (s_ * 0.33 * r, -r * 1.0, 0.0),
                               (s_ * 0.33 * r + 0.12 * r, -r * 0.97, 0.1 * r)], 0.025 * r, mat("trait", NOIR, 0.4))
    else:
        for s_ in (-1, 1):
            x, y, z = surface((0, 0, 0), (r, r, r), s_ * 0.32 * r, 0.12 * r)
            oeil(x, y + 0.04 * r, z, 0.15 * r, "normal", peau=peau)
    for s_ in (-1, 1):
        x, y, z = surface((0, 0, 0), (r, r, r), s_ * 0.55 * r, -0.18 * r)
        sphere("joue", (x, y + 0.02 * r, z), (0.13 * r, 0.04 * r, 0.09 * r), mat("joue_a", "#ff8a65", 0.6))
    x, y, z = surface((0, 0, 0), (r, r, r), 0, -0.32 * r)
    tube("sourire", [(-0.22 * r, y, z + 0.06 * r), (-0.1 * r, y - 0.02, z - 0.06 * r), (0.1 * r, y - 0.02, z - 0.06 * r),
                     (0.22 * r, y, z + 0.06 * r)], 0.03 * r, mat("trait", NOIR, 0.4))


def accessoire(nom):
    if nom == "soleil":
        sphere("soleil", (0, 0, 0), 1.0, mat("soleil", "#ffcf2e", 0.4, emission=0.6))
        visage_astre(1.0, "#ffcf2e")
        rayon = mat("rayon", "#ffae1a", 0.4, emission=0.5)
        for k in range(12):
            a = k * 2 * math.pi / 12
            cone("rayon", (1.42 * math.cos(a), 0.2, 1.42 * math.sin(a)), 0.2, 0.05, 0.5, rayon,
                 rot=(0, -math.degrees(a) + 90, 0), biseau=0.05)
        return 3.6
    if nom == "lune":
        sphere("lune", (0, 0, 0), 1.0, mat("lune", "#fff1b8", 0.5, emission=0.5))
        for dx, dz, r in [(-0.4, -0.35, 0.14), (0.45, 0.4, 0.1), (0.5, -0.45, 0.08)]:
            x, y, z = surface((0, 0, 0), (1, 1, 1), dx, dz)
            sphere("cratere", (x, y + 0.05, z), (r, 0.05, r), mat("cratere", "#f0dc95", 0.6))
        visage_astre(1.0, "#fff1b8", endormi=True)
        return 2.4
    if nom == "etoile":
        bpy.ops.mesh.primitive_circle_add(vertices=10, radius=1.0, fill_type="NGON", rotation=(math.pi / 2, 0, 0))
        o = bpy.context.object
        for i, v in enumerate(o.data.vertices):
            if i % 2:
                v.co *= 0.48
        sol_ = o.modifiers.new("epaisseur", "SOLIDIFY")
        sol_.thickness = 0.35
        b = o.modifiers.new("biseau", "BEVEL")
        b.width = 0.12
        b.segments = 6
        lisser(o)
        o.data.materials.append(mat("etoile", "#ffe066", 0.3, emission=1.2))
        return 2.4
    if nom.startswith("nuage"):
        k = int(nom[-1])
        import random
        rnd = random.Random(k)
        m = mat("nuage", "#ffffff", 0.9, sss=0.3)
        for i in range(7):
            sphere("bosse", (rnd.uniform(-1.1, 1.1), 0, rnd.uniform(-0.1, 0.35)), rnd.uniform(0.5, 0.75), m, seg=40)
        sphere("base", (0, 0, -0.15), (1.6, 0.6, 0.4), m)
        return 4.0
    if nom.startswith("ballon_"):
        c = nom.split("_")[1]
        sphere("ballon", (0, 0, 0.2), (0.7, 0.7, 0.85), mat("ballon_" + c, "#" + c, 0.15, coat=1.0))
        cone("noeud", (0, 0, -0.72), 0.12, 0.02, 0.16, mat("ballon_" + c, "#" + c, 0.15, coat=1.0), rot=(180, 0, 0))
        return 2.2
    raise ValueError(nom)


ACCESSOIRES = ["soleil", "lune", "etoile", "nuage1", "nuage2", "nuage3"] + \
    ["ballon_" + c for c in ("ff5252", "ffa726", "ffee58", "66bb6a", "42a5f5", "ab47bc", "ff80ab")]


def rendre_accessoires(sortie, qualite):
    os.makedirs(sortie, exist_ok=True)
    for nom in ACCESSOIRES:
        vider()
        reglages(512, 512, qualite)
        monde("#dcefff", "#fff4e6", 0.7)
        eclairage_studio()
        echelle = accessoire(nom)
        cam = bpy.data.cameras.new("cam")
        cam.type = "ORTHO"
        cam.ortho_scale = echelle
        o = bpy.data.objects.new("cam", cam)
        bpy.context.collection.objects.link(o)
        o.location = (0, -20, 0)
        o.rotation_euler = (math.pi / 2, 0, 0)
        bpy.context.scene.camera = o
        rendre(os.path.join(sortie, f"{nom}.png"))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    sortie, quoi = argv[0], argv[1]
    qualite = int(argv[2]) if len(argv) > 2 else 64
    if quoi == "persos":
        rendre_persos(sortie, qualite)
    elif quoi.startswith("test:"):
        rendre_persos(sortie, qualite, seulement=quoi[5:].split(","))
    elif quoi == "decors":
        rendre_decors(sortie, qualite)
    elif quoi.startswith("decor:"):
        rendre_decors(sortie, qualite, seulement=quoi[6:].split(","))
    elif quoi == "accessoires":
        rendre_accessoires(sortie, qualite)

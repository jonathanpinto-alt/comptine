"""Modélisation et rendu 3D de « C'est l'heure du bain » — exécuté DANS Blender.

    blender -b --factory-startup -P comptine/bain/blender_bain.py -- <dossier> <quoi> [qualite]

`quoi` : plans | garcon:<plan> | accessoires | test:<pose>

Personnage original : un petit garçon de 2 ans, grosse tête ronde, grands yeux
brillants, boucles blondes, pyjama bleu à étoile jaune. Il est construit par
code (ellipsoïdes, courbes) et posé par cinématique inverse (bras).

Pour chaque cadrage (« plan ») on rend :
  - le décor seul (salle de bain, baignoire, mousse…), opaque ;
  - le garçon dans chaque pose et expression, sur fond transparent, avec tous
    les objets du décor en « holdout » : ce qui le cache (bord de la baignoire,
    eau, mousse) est découpé exactement. Il suffit ensuite de superposer.
Les positions utiles à l'animation 2D (tête, pieds, miroir…) sont projetées à
l'écran et écrites dans meta.json.
"""
import json
import math
import os
import random
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from comptine import blender3d as B3  # noqa: E402
from comptine.blender3d import (D2R, boite, cylindre, hexa, lisser, lumiere_aire, mat,  # noqa: E402
                                sphere, surface, tube)

W, H = 1920, 1080


# ===================================================================== matériaux texturés
def mat_carreaux(nom, c1, c2, mortier, echelle, rot_x=0.0, rough=0.25):
    """Carrelage (texture brique sans décalage) en coordonnées objet."""
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (rot_x, 0, 0)
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Color1"].default_value = hexa(c1)
    br.inputs["Color2"].default_value = hexa(c2)
    br.inputs["Mortar"].default_value = hexa(mortier)
    br.inputs["Scale"].default_value = echelle
    br.inputs["Mortar Size"].default_value = 0.008
    br.inputs["Mortar Smooth"].default_value = 0.3
    br.inputs["Brick Width"].default_value = 0.2
    br.inputs["Row Height"].default_value = 0.2
    br.inputs["Bias"].default_value = -1.0 if c1 == c2 else 0.0
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = 0.3
    return m


def mat_damier(nom, c1, c2, echelle, rough=0.35):
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ch = nt.nodes.new("ShaderNodeTexChecker")
    ch.inputs["Color1"].default_value = hexa(c1)
    ch.inputs["Color2"].default_value = hexa(c2)
    ch.inputs["Scale"].default_value = echelle
    nt.links.new(tc.outputs["Object"], ch.inputs["Vector"])
    nt.links.new(ch.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    return m


def mat_degrade(nom, haut, bas, emission=0.0):
    """Dégradé vertical (vitre, ciel de la fenêtre)."""
    m = bpy.data.materials.new(nom)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rp = nt.nodes.new("ShaderNodeValToRGB")
    rp.color_ramp.elements[0].color = hexa(bas)
    rp.color_ramp.elements[1].color = hexa(haut)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], rp.inputs["Fac"])
    nt.links.new(rp.outputs["Color"], b.inputs["Base Color"])
    if emission:
        nt.links.new(rp.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emission
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Coat Weight"].default_value = 1.0
    return m


# ===================================================================== outils
def objets():
    return set(bpy.data.objects)


def regrouper(nouveaux, nom, pivot):
    """Parente les objets à un « empty » placé au pivot (pour les tourner ensemble)."""
    e = bpy.data.objects.new(nom, None)
    bpy.context.collection.objects.link(e)
    e.location = pivot
    bpy.context.view_layer.update()
    for o in nouveaux:
        if o.parent is None:
            o.parent = e
            o.matrix_parent_inverse = e.matrix_world.inverted()
    return e


def etoile_plate(nom, loc, r, ep, materiau, rot=(90, 0, 0)):
    bpy.ops.mesh.primitive_circle_add(vertices=10, radius=r, fill_type="NGON", location=loc,
                                      rotation=[a * D2R for a in rot])
    o = bpy.context.object
    o.name = nom
    for i, v in enumerate(o.data.vertices):
        if i % 2:
            v.co *= 0.48
    s = o.modifiers.new("ep", "SOLIDIFY")
    s.thickness = ep
    b = o.modifiers.new("biseau", "BEVEL")
    b.width = ep * 0.35
    b.segments = 4
    lisser(o)
    o.data.materials.append(materiau)
    return o


def base_vers(d, n):
    """Matrice de rotation : +Z local -> d (direction des doigts), -Y local -> n (normale de la paume)."""
    ez = Vector(d).normalized()
    ey = -Vector(n)
    ey = (ey - ez * ey.dot(ez)).normalized()
    ex = ey.cross(ez).normalized()
    return Matrix((ex, ey, ez)).transposed().to_4x4()


def transformer(objs, M):
    bpy.context.view_layer.update()          # matrix_world à jour (échelles des sphères)
    for o in objs:
        o.matrix_world = M @ o.matrix_world


# ===================================================================== le petit garçon
PEAU = "#ffd8c0"
PEAU_FONCE = "#ffbea0"
CHEVEUX = ("#f7d56a", "#efc04e", "#fbe28e")
BLEU = "#3f86e8"
BLEU_CLAIR = "#a8d4ff"
BLEU_FONCE = "#2f6fd0"

TETE_C = Vector((0.0, -0.01, 0.76))
TETE_R = (0.30, 0.28, 0.285)
EPAULE = 0.185
L_BRAS, L_AVANT = 0.165, 0.155

EXPRESSIONS = {
    #             yeux       bouche     sourcils
    "timide":    ("normal", "petit", "timide"),
    "sourire":   ("normal", "sourire", "normal"),
    "rit":       ("normal", "rit", "hauts"),
    "rit_ferme": ("heureux", "rit", "hauts"),
    "cligne":    ("cligne", "sourire", "normal"),
    "concentre": ("normal", "langue", "concentre"),
    "brosse":    ("normal", "brosse", "normal"),
    "brosse_cligne": ("cligne", "brosse", "normal"),
}


def oeil_garcon(x, y, z, r0, etat, regard, peau):
    if etat == "heureux":
        r = r0 * 1.22
        pts = [(x - r * 0.75, y - r * 0.05, z - r * 0.2), (x - r * 0.35, y - r * 0.18, z + r * 0.3),
               (x + r * 0.35, y - r * 0.18, z + r * 0.3), (x + r * 0.75, y - r * 0.05, z - r * 0.2)]
        tube("oeil_rieur", pts, r * 0.11, mat("trait", B3.NOIR, 0.4))
        return
    B3.oeil(x, y, z, r0, etat, regard=regard, couleur_iris="#3b7fc4", peau=peau)


def bouche_garcon(y, z, forme, peau_m):
    rouge = mat("bouche_g", "#8a1f2f", 0.5)
    langue = mat("langue_g", "#ff7d97", 0.4, sss=0.2)
    trait = mat("trait_b", "#7a2b2b", 0.4)
    if forme == "sourire":
        tube("sourire", [(-0.07, y + 0.01, z + 0.018), (-0.035, y - 0.004, z - 0.022), (0.035, y - 0.004, z - 0.022),
                         (0.07, y + 0.01, z + 0.018)], 0.0085, trait)
    elif forme == "petit":
        tube("sourire", [(-0.035, y + 0.006, z + 0.006), (-0.015, y - 0.002, z - 0.01), (0.02, y - 0.002, z - 0.008),
                         (0.04, y + 0.006, z + 0.01)], 0.0075, trait)
    elif forme == "rit":
        sphere("bouche", (0, y + 0.012, z - 0.012), (0.068, 0.03, 0.05), rouge)
        sphere("langue", (0, y - 0.004, z - 0.04), (0.045, 0.022, 0.022), langue)
        for s_ in (-1, 1):
            sphere("dent", (s_ * 0.014, y - 0.012, z + 0.026), (0.012, 0.008, 0.01), mat("dent", "#ffffff", 0.2))
        sphere("levre", (0, y + 0.005, z + 0.036), (0.07, 0.022, 0.012), peau_m)
    elif forme == "langue":
        tube("sourire", [(-0.05, y + 0.008, z + 0.012), (-0.02, y - 0.003, z - 0.012), (0.03, y - 0.003, z - 0.012),
                         (0.055, y + 0.008, z + 0.012)], 0.008, trait)
        sphere("langue", (0.035, y - 0.012, z - 0.02), (0.022, 0.018, 0.016), langue)
    elif forme == "brosse":
        sphere("bouche", (0, y + 0.012, z - 0.008), (0.04, 0.03, 0.034), rouge)
        mousse = mat("mousse_dent", "#ffffff", 0.6, sss=0.3)
        rnd = random.Random(3)
        for k in range(9):
            a = k / 9 * 2 * math.pi
            sphere("mousse", (0.05 * math.cos(a) + rnd.uniform(-0.01, 0.01), y - 0.006,
                              z - 0.008 + 0.042 * math.sin(a)), 0.014 + rnd.uniform(0, 0.008), mousse, seg=16)


def tete_garcon(expr, regard=(0, 0), capuche=False, couronne=False):
    """Tête complète (visage, cheveux) ; renvoie la liste des objets créés."""
    avant = objets()
    peau_m = mat("peau", PEAU, 0.5, sss=0.35)
    yeux, forme_bouche, sourcils = EXPRESSIONS[expr]
    C_, R = tuple(TETE_C), TETE_R
    sphere("tete", C_, R, peau_m)
    # oreilles
    for s_ in (-1, 1):
        sphere("oreille", (s_ * 0.285, 0.0, 0.75), (0.045, 0.03, 0.065), peau_m)
        sphere("oreille_in", (s_ * 0.292, -0.012, 0.75), (0.025, 0.02, 0.04), mat("peau_f", PEAU_FONCE, 0.5, sss=0.3))
    # yeux
    for s_ in (-1, 1):
        x, y, z = surface(C_, R, s_ * 0.112, 0.77)
        oeil_garcon(x, y + 0.062 * 0.24, z, 0.064, yeux, regard, PEAU)
    # sourcils
    sc = mat("sourcil", "#d7a84a", 0.6)
    for s_ in (-1, 1):
        x, y, z = surface(C_, R, s_ * 0.112, 0.875)
        if sourcils == "timide":
            dz_in, dz_out = 0.018, -0.006
        elif sourcils == "hauts":
            dz_in, dz_out = 0.012, 0.012
        elif sourcils == "concentre":
            dz_in, dz_out = -0.012, 0.01
        else:
            dz_in, dz_out = 0.0, 0.0
        tube("sourcil", [(x - s_ * 0.045, y + 0.008, z + dz_in), (x, y - 0.004, z + 0.012 + (dz_in + dz_out) / 2),
                         (x + s_ * 0.045, y + 0.008, z + dz_out)], 0.0085, sc)
    # nez, joues
    x, y, z = surface(C_, R, 0, 0.695)
    sphere("nez", (x, y + 0.006, z), (0.034, 0.03, 0.027), mat("nez", "#ffcdb2", 0.45, sss=0.35))
    for s_ in (-1, 1):
        x, y, z = surface(C_, R, s_ * 0.175, 0.665)
        sphere("joue", (x, y + 0.02, z), (0.052, 0.03, 0.036), mat("joue_g", "#ff9eb5", 0.6, sss=0.2))
    x, y, z = surface(C_, R, 0, 0.615)
    bouche_garcon(y, z, forme_bouche, peau_m)
    # boucles blondes
    if not capuche:
        rnd = random.Random(7)
        mats = [mat("cheveux" + c, c, 0.55, sss=0.1) for c in CHEVEUX]
        for i in range(260):
            # points répartis sur la sphère (spirale de Fibonacci)
            k = (i + 0.5) / 260
            el = math.asin(1 - 2 * k)
            az = i * 2.39996
            dx, dy, dz = math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)
            if dz < -0.05:
                continue
            if dy < -0.25 and dz < 0.52:          # visage dégagé
                continue
            if abs(dx) > 0.82 and dz < 0.25:      # oreilles dégagées
                continue
            r = 0.292
            p = (C_[0] + dx * r * 1.02, C_[1] + dy * r, C_[2] + dz * r)
            sphere("boucle", p, rnd.uniform(0.042, 0.056), mats[i % 3], seg=20)
        # frange de petites boucles
        for k in range(7):
            x = -0.16 + k * 0.053
            px, py, pz = surface(C_, R, x, 0.945 + 0.012 * math.sin(k * 1.9))
            sphere("frange", (px, py + 0.022, pz), 0.036 + 0.007 * (k % 2), mats[k % 3], seg=20)
        # boucle signature sur le dessus
        tube("meche", [(0.0, -0.02, 1.06), (0.05, -0.02, 1.13), (0.0, -0.02, 1.17), (-0.04, -0.02, 1.12),
                       (-0.005, -0.02, 1.1)], 0.022, mats[2])
    if couronne:
        mousse = mat("mousse", "#ffffff", 0.7, sss=0.35)
        mousse_r = mat("mousse_rose", "#ffe4f1", 0.7, sss=0.35)
        rnd = random.Random(11)
        for k in range(16):
            a = k / 16 * 2 * math.pi
            p = (C_[0] + 0.24 * math.cos(a), C_[1] + 0.22 * math.sin(a), 1.03 + 0.02 * math.sin(3 * a))
            sphere("couronne", p, rnd.uniform(0.06, 0.085), mousse if k % 3 else mousse_r, seg=20)
        for k in range(6):
            a = k / 6 * 2 * math.pi
            sphere("pointe_couronne", (0.16 * math.cos(a), -0.01 + 0.14 * math.sin(a), 1.12), 0.05, mousse, seg=20)
        sphere("sommet", (0, 0.0, 1.13), 0.07, mousse_r, seg=20)
        for k in range(5):
            sphere("bulle_tete", (rnd.uniform(-0.25, 0.25), -0.2, rnd.uniform(1.0, 1.08)), 0.03, mousse, seg=16)
    if capuche:
        serv = mat("serviette", "#fbfbf6", 0.95, sss=0.15)
        jaune = mat("canard_j", "#ffd84a", 0.6, sss=0.2)
        orange = mat("bec_cap", "#ff9a1f", 0.35, coat=0.3)
        sphere("capuche", (0, 0.08, 0.8), (0.36, 0.3, 0.36), serv)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.3, minor_radius=0.045, location=(0, -0.17, 0.78),
                                         rotation=(math.pi / 2, 0, 0))
        t_ = bpy.context.object
        t_.scale = (1.0, 1.06, 1.0)
        lisser(t_)
        t_.data.materials.append(serv)
        for s_ in (-1, 1):
            sphere("oreille_canard", (s_ * 0.2, 0.05, 1.12), (0.08, 0.05, 0.11), jaune, rot=(0, s_ * -30, 0))
        sphere("bec_capuche", (0, -0.27, 1.07), (0.09, 0.07, 0.035), orange, rot=(-10, 0, 0))
        for s_ in (-1, 1):
            sphere("oeil_capuche", (s_ * 0.1, -0.22, 1.13), (0.028, 0.02, 0.034), mat("pupille", "#120808", 0.1, coat=1.0))
            sphere("reflet_capuche", (s_ * 0.1 + 0.008, -0.245, 1.14), 0.009, mat("reflet", "#ffffff", 0.2, emission=6.0))
        # quelques boucles qui dépassent sur le front
        mats = [mat("cheveux" + c, c, 0.55, sss=0.1) for c in CHEVEUX]
        for k in range(5):
            px, py, pz = surface(C_, R, -0.1 + k * 0.05, 0.93)
            sphere("frange", (px, py + 0.02, pz), 0.045, mats[k % 3], seg=20)
    return [o for o in objets() - avant]


def main_garcon(forme, peau_m, cote):
    """Main construite à l'origine : doigts vers +Z, paume vers -Y."""
    avant = objets()
    if forme == "ouverte":
        sphere("paume", (0, 0, 0), (0.046, 0.022, 0.045), peau_m)
        for k, xo in enumerate((-0.03, -0.01, 0.01, 0.03)):
            a = (k - 1.5) * 9
            lg = 0.042 - 0.006 * abs(k - 1.5)
            cx = xo + math.sin(a * D2R) * lg / 2
            cylindre("doigt", (cx, 0, 0.035 + lg / 2), 0.0115, lg, peau_m, rot=(0, a, 0), sommets=16)
            sphere("bout", (xo + math.sin(a * D2R) * lg, 0, 0.035 + lg), 0.0118, peau_m, seg=16)
        sphere("pouce", (cote * 0.05, -0.005, 0.0), (0.016, 0.014, 0.03), peau_m, rot=(0, cote * -40, 0), seg=16)
    else:
        sphere("poing", (0, 0, 0.01), (0.044, 0.04, 0.046), peau_m)
        sphere("pouce", (cote * 0.035, -0.03, 0.02), (0.014, 0.014, 0.024), peau_m, seg=16)
        if forme == "pointe":
            cylindre("index", (0, -0.01, 0.07), 0.0125, 0.06, peau_m, sommets=16)
            sphere("bout", (0, -0.01, 0.1), 0.0128, peau_m, seg=16)
    return [o for o in objets() - avant]


def bras(cote, main_pos, d_main, n_main, forme, tenue, coude=None):
    """Bras (épaule -> coude -> poignet) par cinématique inverse, puis la main orientée."""
    peau_m = mat("peau", PEAU, 0.5, sss=0.35)
    S = Vector((cote * EPAULE, 0.0, 0.53))
    d = Vector(d_main).normalized()
    Wp = Vector(main_pos) - d * 0.045                       # poignet
    u = Wp - S
    dist = min(u.length, L_BRAS + L_AVANT - 0.005)
    u.normalize()
    pole = Vector(coude or (cote * 0.6, 0.35, -1.0)).normalized()
    p = (pole - u * pole.dot(u)).normalized()
    a = math.acos(max(-1, min(1, (L_BRAS ** 2 + dist ** 2 - L_AVANT ** 2) / (2 * L_BRAS * dist))))
    E = S + L_BRAS * (math.cos(a) * u + math.sin(a) * p)
    Wp = S + u * dist
    if tenue == "pyjama":
        manche, r = mat("pyjama", BLEU, 0.6, sss=0.1), 0.056
    elif tenue == "serviette":
        manche, r = mat("serviette", "#fbfbf6", 0.95, sss=0.15), 0.06
    else:
        manche, r = peau_m, 0.047
    # bras en deux segments arrondis (plus fiable qu'une courbe pour les coudes pliés)
    for A, Bv, nom in ((S, E, "bras"), (E, Wp, "avant_bras")):
        v = Bv - A
        o = cylindre(nom, tuple((A + Bv) / 2), r, v.length, manche, sommets=24)
        o.rotation_euler = v.to_track_quat("Z", "Y").to_euler()
    sphere("coude", tuple(E), r, manche, seg=24)
    sphere("epaule", tuple(S), r * 1.1, manche, seg=24)
    if tenue == "pyjama":
        o = cylindre("poignet", tuple(Wp - (Wp - E).normalized() * 0.01), r * 1.08, 0.028,
                     mat("pyjama_clair", BLEU_CLAIR, 0.6), sommets=24)
        o.rotation_euler = (Wp - E).to_track_quat("Z", "Y").to_euler()
    sphere("poignet_peau", tuple(Wp), 0.036, peau_m, seg=20)
    objs = main_garcon(forme, peau_m, cote)
    # main au bout du bras réel (si la cible est hors de portée, elle se rapproche)
    transformer(objs, Matrix.Translation(Wp + d * 0.045) @ base_vers(d, n_main))
    return objs


def corps_garcon(tenue):
    peau_m = mat("peau", PEAU, 0.5, sss=0.35)
    if tenue == "pyjama":
        bleu = mat("pyjama", BLEU, 0.6, sss=0.1)
        clair = mat("pyjama_clair", BLEU_CLAIR, 0.6)
        sphere("ventre", (0, 0.0, 0.37), (0.235, 0.2, 0.25), bleu)
        sphere("bassin", (0, 0.01, 0.21), (0.215, 0.18, 0.12), mat("pyjama_f", BLEU_FONCE, 0.6, sss=0.1))
        for s_ in (-1, 1):
            cylindre("jambe", (s_ * 0.095, 0.0, 0.12), 0.082, 0.2, mat("pyjama_f", BLEU_FONCE, 0.6, sss=0.1), biseau=0.03)
            cylindre("cheville", (s_ * 0.095, 0.0, 0.035), 0.085, 0.03, clair, biseau=0.01)
            sphere("pied", (s_ * 0.1, -0.05, 0.03), (0.07, 0.11, 0.045), peau_m)
            for k in range(4):
                sphere("orteil", (s_ * 0.1 + (k - 1.5) * 0.024 * s_, -0.15, 0.03), 0.017, peau_m, seg=12)
        for s_ in (-1, 1):
            sphere("col", (s_ * 0.075, -0.15, 0.585), (0.085, 0.035, 0.05), mat("col", "#ffffff", 0.6), rot=(20, 0, s_ * 25))
        for z in (0.47, 0.39, 0.31):
            x, y, zz = surface((0, 0, 0.37), (0.235, 0.2, 0.25), 0, z)
            sphere("bouton", (x, y + 0.005, zz), (0.017, 0.01, 0.017), mat("bouton", "#ffffff", 0.3, coat=0.5), seg=16)
        x, y, z = surface((0, 0, 0.37), (0.235, 0.2, 0.25), 0.11, 0.43)
        e = etoile_plate("etoile", (x, y - 0.005, z), 0.055, 0.02, mat("etoile_j", "#ffd23f", 0.4, coat=0.3))
        e.rotation_euler = (90 * D2R, 0, -25 * D2R)
    elif tenue == "nu":
        sphere("ventre", (0, 0.0, 0.37), (0.225, 0.19, 0.25), peau_m)
        for s_ in (-1, 1):
            sphere("teton", (s_ * 0.08, -0.175, 0.46), (0.012, 0.005, 0.012), mat("peau_f", PEAU_FONCE, 0.5, sss=0.3), seg=12)
    elif tenue == "serviette":
        serv = mat("serviette", "#fbfbf6", 0.95, sss=0.15)
        sphere("poncho", (0, 0.0, 0.36), (0.27, 0.23, 0.3), serv)
        sphere("bas_poncho", (0, 0.0, 0.2), (0.29, 0.25, 0.12), serv)
        bord = mat("bord_serviette", "#ffd84a", 0.8)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.26, minor_radius=0.022, location=(0, 0, 0.11))
        t_ = bpy.context.object
        lisser(t_)
        t_.data.materials.append(bord)
        for s_ in (-1, 1):
            cylindre("jambe", (s_ * 0.09, 0.0, 0.07), 0.07, 0.12, peau_m, biseau=0.02)
            sphere("pied", (s_ * 0.1, -0.05, 0.03), (0.07, 0.11, 0.045), peau_m)
            for k in range(4):
                sphere("orteil", (s_ * 0.1 + (k - 1.5) * 0.024 * s_, -0.15, 0.03), 0.017, peau_m, seg=12)


def garcon(tenue, expr, pose):
    """Construit le garçon (repère local : sol à z=0, face vers -Y) et le place dans la scène.

    pose : dict(mains=((pos, dir, normale, forme), (pos, dir, normale, forme)),
                tete=(rx, ry, rz) degrés, regard=(gx, gz), lieu=(x, y, z), rot_z=degrés,
                couronne=bool, brosse=bool)"""
    avant = objets()
    corps_garcon(tenue)
    for cote, (pos, d, n, forme, *reste) in zip((-1, 1), pose["mains"]):
        bras(cote, pos, d, n, forme, tenue, coude=reste[0] if reste else None)
    if pose.get("brosse"):
        brosse_a_dents(pose["mains"][1])
    corps = [o for o in objets() - avant]
    tete = tete_garcon(expr, pose.get("regard", (0, 0)), capuche=tenue == "serviette",
                       couronne=pose.get("couronne", False))
    e_tete = regrouper(tete, "pivot_tete", (0, 0, 0.55))
    rx, ry, rz = pose.get("tete", (0, 0, 0))
    e_tete.rotation_euler = (rx * D2R, ry * D2R, rz * D2R)
    racine = regrouper(corps + [e_tete], "garcon", (0, 0, 0))
    racine.location = pose.get("lieu", (0, 0, 0))
    racine.rotation_euler = (0, 0, pose.get("rot_z", 0) * D2R)
    s_ = pose.get("echelle", 1.0)
    racine.scale = (s_, s_, s_)
    bpy.context.view_layer.update()
    return racine, [o for o in objets() - avant]


def brosse_a_dents(main):
    pos, d, n, _f, *_ = main
    avant = objets()
    manche = mat("brosse", "#4fc3f7", 0.3, coat=0.5)
    cylindre("manche", (0, 0, 0.0), 0.012, 0.19, manche, rot=(0, 90, 0), sommets=16)
    boite("tete_brosse", (-0.1, 0.0, 0.0), (0.03, 0.022, 0.018), manche, biseau=0.006)
    boite("poils", (-0.1, 0.0, 0.017), (0.028, 0.02, 0.022), mat("poils", "#ffffff", 0.6), biseau=0.004)
    sphere("dentifrice", (-0.1, 0.0, 0.034), (0.016, 0.012, 0.01), mat("pate", "#7fd8ff", 0.4), seg=16)
    objs = [o for o in objets() - avant]
    # la brosse traverse le poing horizontalement, la tête vers la bouche (-X local)
    transformer(objs, Matrix.Translation(Vector(pos)) @ Matrix.Rotation(-8 * D2R, 4, "Y"))


# ===================================================================== décors
def piece(mur="#9fe3e0", mur_haut="#fff3c8", sol1="#cdeeff", sol2="#ffffff", fond_y=1.4):
    """Sol en damier, mur du fond carrelé (bas) et peint (haut), plinthe."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    s = bpy.context.object
    s.scale = (14, 10, 1)
    bpy.ops.object.transform_apply(scale=True)
    s.data.materials.append(mat_damier("sol", sol1, sol2, 1.6))
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, fond_y, 0.6), rotation=(math.pi / 2, 0, 0))
    m = bpy.context.object
    m.scale = (14, 1.2, 1)
    bpy.ops.object.transform_apply(scale=True)
    m.data.materials.append(mat_carreaux("carrelage", mur, mur, "#ffffff", 1.0, rot_x=0.0))
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, fond_y, 2.6), rotation=(math.pi / 2, 0, 0))
    m = bpy.context.object
    m.scale = (14, 2.8, 1)
    m.data.materials.append(mat(f"peinture{mur_haut}", mur_haut, 0.85))
    boite("frise", (0, fond_y - 0.02, 1.22), (14, 0.05, 0.06), mat("frise", "#ff8fb8", 0.4, coat=0.3), biseau=0.02)
    for k in range(-12, 13):
        etoile_plate("etoile_mur", (k * 0.55, fond_y - 0.03, 1.22), 0.05, 0.02,
                     mat("etoile_mur" + str(k % 3), ["#ffd23f", "#7fd8ff", "#b388ff"][k % 3], 0.4))


BAIGNOIRE = dict(x=0.0, y=0.25, L=1.75, l=0.86, h=0.56)


def baignoire(x=0.0, y=0.25, montagne=False, graine=1):
    b = BAIGNOIRE
    blanc = mat("emaille", "#ffffff", 0.12, coat=0.8)
    boite("baignoire", (x, y, 0.07 + b["h"] / 2), (b["L"], b["l"], b["h"]), blanc, biseau=0.14)
    boite("rebord", (x, y, 0.07 + b["h"] - 0.02), (b["L"] + 0.06, b["l"] + 0.06, 0.07), blanc, biseau=0.035)
    rayure = mat("rayure", "#ffb3d1", 0.3, coat=0.6)
    boite("rayure", (x, y - b["l"] / 2 - 0.002, 0.33), (b["L"] - 0.24, 0.01, 0.06), rayure, biseau=0.004)
    dore = mat("pied_dore", "#ffcf4a", 0.25, metal=0.6, coat=0.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            sphere("pied_b", (x + sx * (b["L"] / 2 - 0.18), y + sy * (b["l"] / 2 - 0.12), 0.06), (0.07, 0.07, 0.07), dore)
    eau = mat("eau", "#8fdcff", 0.05, coat=1.0, spec=0.8)
    zl = 0.07 + b["h"] - 0.035
    boite("eau", (x, y, zl - 0.01), (b["L"] - 0.12, b["l"] - 0.12, 0.02), eau, biseau=0.008)
    # robinet
    chrome = mat("chrome", "#e8f0ff", 0.12, metal=0.9)
    cylindre("robinet", (x + b["L"] / 2 - 0.12, y + b["l"] / 2 - 0.05, zl + 0.15), 0.025, 0.3, chrome)
    tube("bec_robinet", [(x + b["L"] / 2 - 0.12, y + b["l"] / 2 - 0.05, zl + 0.29),
                         (x + b["L"] / 2 - 0.12, y + b["l"] / 2 - 0.2, zl + 0.33),
                         (x + b["L"] / 2 - 0.12, y + b["l"] / 2 - 0.26, zl + 0.22)], 0.022, chrome)
    for k, c in enumerate(("#ff6b6b", "#6bb8ff")):
        sphere("poignee", (x + b["L"] / 2 - 0.2 + k * 0.16, y + b["l"] / 2 - 0.05, zl + 0.12), 0.035, mat("p" + c, c, 0.3, coat=0.5))
    mousse(x, y, zl, montagne, graine)
    return zl


def mousse(x, y, zl, montagne, graine):
    """Mousse sur l'eau : grappes de sphères blanches et pastel, en couronne autour du centre."""
    rnd = random.Random(graine)
    b = BAIGNOIRE
    m = [mat("mousse", "#ffffff", 0.7, sss=0.35), mat("mousse_rose", "#ffe4f1", 0.7, sss=0.35),
         mat("mousse_bleue", "#e3f4ff", 0.7, sss=0.35)]
    n = 150 if montagne else 120
    for k in range(n):
        px = rnd.uniform(-b["L"] / 2 + 0.15, b["L"] / 2 - 0.15)
        py = rnd.uniform(-b["l"] / 2 + 0.12, b["l"] / 2 - 0.12)
        if not montagne and abs(px) < 0.32 and py < 0.2:
            px += 0.42 * (1 if px >= 0 else -1)          # place libre pour le garçon
        h = 0.0
        if montagne:
            h = 0.32 * math.exp(-((px - 0.1) ** 2 / 0.25 + py ** 2 / 0.12))
        r = rnd.uniform(0.05, 0.11)
        sphere("mousse", (x + px, y + py, zl + 0.02 + h * rnd.uniform(0.6, 1.0)), r, m[k % 3], seg=20)
    if not montagne:
        # collier de mousse devant le garçon (cache la ligne d'eau sur son ventre)
        for k in range(15):
            a = math.pi * (1.1 + 0.8 * k / 14)
            px, py = 0.27 * math.cos(a) * 1.25, 0.18 + 0.24 * math.sin(a)
            sphere("mousse_col", (x + px, y - 0.25 + py, zl + 0.03), rnd.uniform(0.06, 0.085), m[k % 3], seg=20)


def etagere(x, y, z):
    bois = mat("etagere", "#ffffff", 0.4, coat=0.3)
    boite("planche", (x, y, z), (0.9, 0.18, 0.04), bois, biseau=0.015)
    cols = ["#ff7eb6", "#7fd8ff", "#ffd23f", "#9b8cff"]
    for k, c in enumerate(cols):
        h = 0.18 + 0.05 * (k % 2)
        cylindre("flacon", (x - 0.3 + k * 0.2, y, z + 0.02 + h / 2), 0.05, h, mat("flacon" + c, c, 0.2, coat=0.8), biseau=0.02)
        sphere("bouchon", (x - 0.3 + k * 0.2, y, z + 0.03 + h), 0.032, mat("bouchon", "#ffffff", 0.3))


def porte_serviette(x, y, z, couleur="#ff9ecb"):
    chrome = mat("chrome", "#e8f0ff", 0.12, metal=0.9)
    cylindre("barre", (x, y - 0.06, z), 0.018, 0.7, chrome, rot=(0, 90, 0))
    serv = mat("serviette_" + couleur, couleur, 0.95, sss=0.1)
    boite("serviette", (x, y - 0.08, z - 0.3), (0.55, 0.05, 0.6), serv, biseau=0.03)
    boite("bande", (x, y - 0.108, z - 0.5), (0.55, 0.01, 0.06), mat("bande", "#ffffff", 0.9), biseau=0.005)


def fenetre_nuit(x, y, z, r=0.42):
    cadre = mat("cadre_fenetre", "#ffffff", 0.35, coat=0.3)
    bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=0.05, location=(x, y - 0.03, z),
                                     rotation=(math.pi / 2, 0, 0))
    t_ = bpy.context.object
    lisser(t_)
    t_.data.materials.append(cadre)
    cylindre("ciel_nuit", (x, y - 0.01, z), r, 0.02, mat_degrade("ciel_nuit", "#2b2d7a", "#7b5cc4", emission=1.0),
             rot=(90, 0, 0))
    sphere("lune_f", (x + r * 0.35, y - 0.04, z + r * 0.3), (0.09, 0.02, 0.09), mat("lune_f", "#fff1b8", 0.5, emission=1.5))
    rnd = random.Random(4)
    for k in range(7):
        etoile_plate("etoile_f", (x + rnd.uniform(-r * 0.7, r * 0.3), y - 0.035, z + rnd.uniform(-r * 0.6, r * 0.5)),
                     0.025, 0.01, mat("etoile_f", "#ffe680", 0.4, emission=2.0))
    boite("croisillon_v", (x, y - 0.04, z), (0.03, 0.02, 2 * r), cadre, biseau=0.008)
    boite("croisillon_h", (x, y - 0.04, z), (2 * r, 0.02, 0.03), cadre, biseau=0.008)


def plante(x, y):
    cylindre("pot", (x, y, 0.15), 0.14, 0.3, mat("pot", "#ff8a65", 0.4, coat=0.3), biseau=0.03)
    f = mat("feuille", "#4caf50", 0.5, sss=0.15)
    for k in range(7):
        a = k / 7 * 2 * math.pi
        sphere("feuille", (x + 0.1 * math.cos(a), y + 0.1 * math.sin(a), 0.45 + 0.08 * (k % 2)), (0.07, 0.07, 0.17), f,
               rot=(25 * math.sin(a), 25 * math.cos(a), 0))


def tapis(x, y):
    boite("tapis", (x, y, 0.012), (0.95, 0.6, 0.02), mat("tapis", "#ffd23f", 0.95), biseau=0.01)
    for k in range(5):
        sphere("pois_tapis", (x - 0.36 + k * 0.18, y + 0.15 * (1 if k % 2 else -1), 0.02), (0.05, 0.05, 0.008),
               mat("pois_tapis", "#ff8fb8", 0.9), seg=16)


def lavabo(x, y):
    blanc = mat("emaille", "#ffffff", 0.12, coat=0.8)
    cylindre("colonne", (x, y, 0.4), 0.13, 0.8, blanc, biseau=0.04)
    sphere("vasque", (x, y - 0.05, 0.86), (0.42, 0.3, 0.13), blanc)
    boite("plan", (x, y + 0.05, 0.96), (0.95, 0.42, 0.05), blanc, biseau=0.02)
    chrome = mat("chrome", "#e8f0ff", 0.12, metal=0.9)
    cylindre("robinet_l", (x, y + 0.2, 1.06), 0.022, 0.16, chrome)
    tube("bec_l", [(x, y + 0.2, 1.14), (x, y + 0.08, 1.17), (x, y + 0.03, 1.1)], 0.018, chrome)
    # verre à dents avec brosses
    cylindre("verre", (x - 0.33, y + 0.08, 1.06), 0.05, 0.15, mat("verre_rose", "#ffb3d1", 0.15, coat=0.8), biseau=0.01)
    for k, c in enumerate(("#ffd23f", "#7ce08a")):
        cylindre("brosse_verre", (x - 0.34 + 0.03 * k, y + 0.08, 1.17), 0.01, 0.2, mat("bv" + c, c, 0.3), rot=(0, 12 - 24 * k, 0))
    # tube de dentifrice
    boite("dentifrice", (x + 0.3, y + 0.0, 1.0), (0.2, 0.06, 0.035), mat("tube_d", "#ffffff", 0.3), biseau=0.015)
    cylindre("bouchon_d", (x + 0.41, y + 0.0, 1.0), 0.02, 0.03, mat("bouchon_d", "#4fc3f7", 0.3), rot=(0, 90, 0))


def miroir_rigolo(x, y, z, rx=0.42, rz=0.52):
    """Miroir ovale avec un cadre en grosses perles pastel et deux yeux rigolos en haut."""
    cols = ["#ff8fb8", "#ffd23f", "#7fd8ff", "#b388ff", "#7ce08a", "#ffab6b"]
    n = 22
    for k in range(n):
        a = k / n * 2 * math.pi
        sphere("perle", (x + (rx + 0.06) * math.cos(a), y - 0.04, z + (rz + 0.06) * math.sin(a)),
               0.075 + 0.01 * math.sin(k * 2.1), mat("perle" + cols[k % 6], cols[k % 6], 0.25, coat=0.6), seg=24)
    vitre = mat_degrade("vitre_miroir", "#e9fbff", "#a9dcff", emission=0.25)
    o = cylindre("vitre", (x, y - 0.02, z), 1.0, 0.02, vitre, rot=(90, 0, 0), sommets=64)
    o.scale = (rx, rz, 1)
    for s_ in (-1, 1):
        B3.oeil(x + s_ * 0.13, y - 0.12, z + rz + 0.16, 0.085, "normal", regard=(-0.4, -0.3), couleur_iris="#5a3418")
    tube("sourire_miroir", [(x - 0.1, y - 0.08, z - rz - 0.1), (x - 0.04, y - 0.1, z - rz - 0.14),
                            (x + 0.04, y - 0.1, z - rz - 0.14), (x + 0.1, y - 0.08, z - rz - 0.1)], 0.015,
         mat("trait", B3.NOIR, 0.4))
    return [(x + rx * math.cos(a), y - 0.035, z + rz * math.sin(a)) for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2)]


def tabouret(x, y):
    m = mat("tabouret", "#7ce08a", 0.4, coat=0.4)
    boite("assise", (x, y, 0.2), (0.45, 0.32, 0.06), m, biseau=0.03)
    for s_ in (-1, 1):
        boite("pied_t", (x + s_ * 0.17, y, 0.1), (0.06, 0.3, 0.2), m, biseau=0.02)


# ===================================================================== plans (cadrages)
LUMIERE = float(os.environ.get("BAIN_LUMIERE", "1.0"))


def eclairage_salle(chaud=1.0):
    k = LUMIERE
    B3.monde("#fff6e8", "#ffe9f2", 0.35 * k)
    lumiere_aire("cle", (-2.5, -4.5, 3.6), (0, 0.3, 0.7), 260 * chaud * k, 3.5, "#fff1de")
    lumiere_aire("contre", (2.2, 0.9, 3.0), (0, 0, 0.9), 90 * k, 2.0, "#e8f1ff")
    lumiere_aire("debouche", (3.5, -3.5, 1.5), (0, 0, 0.7), 70 * k, 4, "#ffe9f2")


def camera_plan(lieu, cible, focale):
    return B3.camera_decor(lieu, cible, focale)


# plan -> (lieu caméra, cible, focale, emplacement du garçon)
PLANS = {
    "large":  ((0.0, -5.0, 1.45), (0.05, 0.3, 0.72), 40, dict(lieu=(-0.85, -0.55, 0.0))),
    "bain":   ((0.0, -3.0, 1.55), (0.0, 0.25, 0.78), 38, dict(lieu=(0.0, 0.18, 0.3))),
    "proche": ((0.05, -1.75, 1.22), (0.0, 0.2, 0.98), 40, dict(lieu=(0.0, 0.18, 0.3))),
    "lavabo": ((-0.2, -3.9, 1.5), (0.05, 0.3, 1.08), 36, dict(lieu=(-0.55, -0.15, 0.24), rot_z=48)),
}


def construire_plan(nom):
    eclairage_salle()
    cam_lieu, cible, focale, _ = PLANS[nom]
    if nom in ("large", "bain", "proche"):
        piece()
        baignoire(0.95 if nom == "large" else 0.0, 0.25, montagne=nom == "large", graine=3)
        if nom == "large":
            tapis(-0.85, -0.5)
            etagere(-1.2, 1.3, 1.55)
            porte_serviette(-2.3, 1.4, 1.35)
            fenetre_nuit(1.0, 1.4, 1.85)
            plante(-2.6, 0.6)
        else:
            etagere(-0.55, 1.3, 1.5)
            fenetre_nuit(0.75, 1.4, 1.8, 0.36)
            porte_serviette(-1.9, 1.4, 1.35)
    else:
        piece(mur="#ffd6e8", mur_haut="#e9f3ff", sol1="#fff3c8", sol2="#ffffff", fond_y=0.8)
        lavabo(0.55, 0.45)
        coins = miroir_rigolo(0.6, 0.78, 1.6, rx=0.36, rz=0.44)
        tabouret(-0.55, -0.15)
        porte_serviette(-1.6, 0.8, 1.35, "#7fd8ff")
        fenetre_nuit(-1.3, 0.8, 1.95, 0.3)
        G_META["vitre"] = coins
    cam = camera_plan(cam_lieu, cible, focale)
    return cam


G_META = {}


def ecran(cam, p):
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    v = world_to_camera_view(sc, cam, Vector(p))
    return [round(v.x * W, 1), round((1 - v.y) * H, 1)]


# ===================================================================== poses
def M(pos, d, n, forme="ouverte", coude=None):
    return (pos, d, n, forme, coude) if coude else (pos, d, n, forme)


BAS_G = M((-0.24, -0.06, 0.27), (0, 0, -1), (1, 0, 0), "ouverte")
BAS_D = M((0.24, -0.06, 0.27), (0, 0, -1), (-1, 0, 0), "ouverte")

POSES = {
    # scène 1 : debout, timide, regarde la baignoire (à droite)
    "timide_a": ("large", "pyjama", dict(
        mains=(M((-0.04, -0.25, 0.35), (0.6, -0.2, -1), (1, 0, 0), "poing"), M((0.045, -0.25, 0.34), (-0.6, -0.2, -1), (-1, 0, 0), "poing")),
        tete=(-6, -4, 22), regard=(0.7, -0.1), rot_z=12), ["timide", "cligne", "sourire"]),
    "timide_b": ("large", "pyjama", dict(
        mains=(BAS_G, M((0.05, -0.29, 0.62), (-0.3, -0.3, 1), (0, 1, 0), "pointe", (1, 0.2, -1))),
        tete=(-8, 6, 14), regard=(0.6, 0.0), rot_z=8), ["timide", "cligne"]),
    # scène 5 : sort du bain dans sa serviette à capuche de canard, saute de joie
    "serviette_a": ("large", "serviette", dict(
        mains=(M((-0.26, -0.16, 0.33), (0, 0, -1), (1, 0, 0)), M((0.26, -0.16, 0.33), (0, 0, -1), (-1, 0, 0))),
        tete=(4, 0, 0), regard=(0, 0.1)), ["rit", "cligne"]),
    "serviette_b": ("large", "serviette", dict(
        mains=(M((-0.36, -0.1, 0.85), (-0.4, 0, 1), (0, 1, 0), "ouverte", (-1, 0.3, -0.3)),
               M((0.36, -0.1, 0.85), (0.4, 0, 1), (0, 1, 0), "ouverte", (1, 0.3, -0.3))),
        tete=(10, 0, 0), regard=(0, 0.3)), ["rit_ferme", "rit"]),
    # scène 2 : dans le bain, il éclabousse
    "eclabousse_a": ("bain", "nu", dict(
        mains=(M((-0.36, -0.2, 0.62), (-0.3, -0.2, 1), (0, 1, 0), "ouverte", (-1, 0.4, -0.5)),
               M((0.36, -0.2, 0.62), (0.3, -0.2, 1), (0, 1, 0), "ouverte", (1, 0.4, -0.5))),
        tete=(6, 0, 0)), ["rit", "rit_ferme"]),
    "eclabousse_b": ("bain", "nu", dict(
        mains=(M((-0.4, -0.25, 0.36), (-0.3, -0.5, 0), (0, 0, -1)), M((0.4, -0.25, 0.36), (0.3, -0.5, 0), (0, 0, -1))),
        tete=(-4, 0, 0)), ["rit_ferme", "rit"]),
    "eclabousse_c": ("bain", "nu", dict(
        mains=(M((-0.38, -0.28, 0.48), (-0.2, -0.6, 0.4), (0, 0.3, -1)), M((0.38, -0.28, 0.48), (0.2, -0.6, 0.4), (0, 0.3, -1))),
        tete=(2, 0, 0)), ["rit", "cligne"]),
    # scène 3 : gros plan, il se frotte les mains puis les montre, fier
    "frotte_a": ("proche", "nu", dict(
        mains=(M((-0.02, -0.3, 0.46), (0.3, -0.2, 0.9), (1, 0, 0)), M((0.035, -0.31, 0.43), (-0.3, -0.2, 0.9), (-1, 0, 0))),
        tete=(-10, 0, 0), regard=(0, -0.8), mousse_mains=True), ["sourire", "cligne"]),
    "frotte_b": ("proche", "nu", dict(
        mains=(M((-0.04, -0.31, 0.43), (0.3, -0.2, 0.9), (1, 0, 0)), M((0.02, -0.3, 0.47), (-0.3, -0.2, 0.9), (-1, 0, 0))),
        tete=(-10, 0, 0), regard=(0, -0.8), mousse_mains=True), ["sourire", "cligne"]),
    "montre": ("proche", "nu", dict(
        mains=(M((-0.2, -0.3, 0.66), (-0.15, 0, 1), (0, -1, 0)), M((0.2, -0.3, 0.66), (0.15, 0, 1), (0, -1, 0))),
        tete=(4, 0, 0)), ["rit", "cligne"]),
    # scène 4 : il se lave les cheveux, couronne de mousse
    "cheveux_a": ("bain", "nu", dict(
        mains=(M((-0.24, -0.06, 1.0), (0.5, 0, 0.6), (1, 0, -0.3)), M((0.25, -0.04, 0.98), (-0.5, 0, 0.6), (-1, 0, -0.3))),
        tete=(0, 6, 8), regard=(0.5, 0.1), couronne=True), ["rit", "rit_ferme"]),
    "cheveux_b": ("bain", "nu", dict(
        mains=(M((-0.26, -0.04, 0.97), (0.5, 0, 0.6), (1, 0, -0.3)), M((0.23, -0.06, 1.01), (-0.5, 0, 0.6), (-1, 0, -0.3))),
        tete=(0, -4, 12), regard=(0.6, 0.1), couronne=True), ["rit_ferme", "rit"]),
    # scène 6 : il compte les bulles en pointant du doigt
    "compte_1": ("bain", "nu", dict(
        mains=(M((-0.44, -0.18, 0.7), (-0.7, -0.3, 0.8), (0, 1, 0), "pointe", (-1, 0.3, -1)),
               M((0.3, -0.24, 0.36), (0, -0.3, -1), (-1, 0, 0))),
        tete=(10, 0, -12), regard=(-0.6, 0.6)), ["concentre", "rit"]),
    "compte_2": ("bain", "nu", dict(
        mains=(M((-0.3, -0.24, 0.36), (0, -0.3, -1), (1, 0, 0)),
               M((0.34, -0.12, 0.86), (0.05, -0.2, 1), (0, 1, 0), "pointe", (1, 0.3, -1))),
        tete=(12, 0, 4), regard=(0.25, 0.8)), ["concentre", "rit"]),
    "compte_3": ("bain", "nu", dict(
        mains=(M((-0.3, -0.24, 0.36), (0, -0.3, -1), (1, 0, 0)),
               M((0.44, -0.18, 0.7), (0.7, -0.3, 0.8), (0, 1, 0), "pointe", (1, 0.3, -1))),
        tete=(10, 0, 12), regard=(0.7, 0.6)), ["concentre", "rit"]),
    # scène 7 : en pyjama propre, il se brosse les dents devant le miroir
    "brosse_a": ("lavabo", "pyjama", dict(
        mains=(M((-0.22, -0.12, 0.3), (0, 0, -1), (1, 0, 0)), M((0.06, -0.33, 0.62), (0, 0, 1), (0, 1, 0), "poing", (1, 0, -1))),
        tete=(0, 0, 10), regard=(0.8, 0.1), brosse=True), ["brosse", "brosse_cligne"]),
    "brosse_b": ("lavabo", "pyjama", dict(
        mains=(M((-0.22, -0.12, 0.3), (0, 0, -1), (1, 0, 0)), M((0.0, -0.33, 0.63), (0, 0, 1), (0, 1, 0), "poing", (1, 0, -1))),
        tete=(0, 0, 10), regard=(0.8, 0.1), brosse=True), ["brosse", "brosse_cligne"]),
    # reflet dans le miroir : vu de face (puis retourné en 2D)
    "reflet_a": ("lavabo", "pyjama", dict(
        mains=(M((-0.22, -0.12, 0.3), (0, 0, -1), (1, 0, 0)), M((0.06, -0.33, 0.62), (0, 0, 1), (0, 1, 0), "poing", (1, 0, -1))),
        tete=(0, 0, 0), regard=(0.0, 0.0), brosse=True, rot_z=0), ["brosse"]),
    "reflet_b": ("lavabo", "pyjama", dict(
        mains=(M((-0.22, -0.12, 0.3), (0, 0, -1), (1, 0, 0)), M((0.0, -0.33, 0.63), (0, 0, 1), (0, 1, 0), "poing", (1, 0, -1))),
        tete=(0, 0, 0), regard=(0.0, 0.0), brosse=True, rot_z=0), ["brosse"]),
}


def mousse_mains(racine_pose):
    """Mousse de savon entre les mains (scène 3)."""
    m = mat("mousse", "#ffffff", 0.7, sss=0.35)
    rnd = random.Random(5)
    (p1, *_), (p2, *_) = racine_pose["mains"]
    c = (Vector(p1) + Vector(p2)) / 2
    avant = objets()
    for k in range(14):
        sphere("mousse_main", (c.x + rnd.uniform(-0.08, 0.08), c.y + rnd.uniform(-0.05, 0.02), c.z + rnd.uniform(-0.06, 0.07)),
               rnd.uniform(0.02, 0.04), m, seg=16)
    return [o for o in objets() - avant]


# ===================================================================== rendus
def preparer_rendu(qualite, transparent):
    B3.reglages(W, H, qualite, transparent=transparent)
    sc = bpy.context.scene
    sc.render.resolution_percentage = int(os.environ.get("BAIN_POURCENT", "100"))
    sc.eevee.use_bloom = True
    sc.eevee.bloom_intensity = 0.02
    sc.view_settings.look = "None"


def rendre_plans(sortie, qualite, seulement=None):
    os.makedirs(sortie, exist_ok=True)
    meta = {}
    for nom in PLANS:
        if seulement and nom not in seulement:
            continue
        B3.vider()
        G_META.clear()
        preparer_rendu(qualite, transparent=False)
        cam = construire_plan(nom)
        B3.rendre(os.path.join(sortie, f"plan_{nom}.png"))
        info = {}
        if "vitre" in G_META:
            info["vitre"] = [ecran(cam, p) for p in G_META["vitre"]]
        b = BAIGNOIRE
        info["eau_z"] = 0.07 + b["h"] - 0.035
        meta[nom] = info
    chemin = os.path.join(sortie, "plans.json")
    ancien = json.load(open(chemin)) if os.path.exists(chemin) else {}
    ancien.update(meta)
    with open(chemin, "w") as fh:
        json.dump(ancien, fh, indent=1)


def rendre_garcon(sortie, qualite, plan, seulement=None):
    """Toutes les poses d'un plan : décor en holdout, garçon seul sur fond transparent."""
    os.makedirs(sortie, exist_ok=True)
    B3.vider()
    G_META.clear()
    preparer_rendu(qualite, transparent=True)
    cam = construire_plan(plan)
    for o in bpy.context.scene.objects:
        if o.type in ("MESH", "CURVE", "META"):
            o.is_holdout = True
    meta = {}
    for nom, (pl, tenue, pose, expressions) in POSES.items():
        if pl != plan or (seulement and nom not in seulement):
            continue
        pose = dict(PLANS[plan][3], **pose)
        for expr in expressions:
            racine, objs = garcon(tenue, expr, pose)
            if pose.get("mousse_mains"):
                extra = mousse_mains(pose)
                for o in extra:
                    o.parent = racine
                    o.matrix_parent_inverse = racine.matrix_world.inverted()
                objs += extra
            B3.rendre(os.path.join(sortie, f"{nom}__{expr}.png"))
            mw = racine.matrix_world
            tete = mw @ (TETE_C + Vector((0, 0, 0)))
            meta[nom] = dict(plan=plan, tete=ecran(cam, tete), pieds=ecran(cam, mw @ Vector((0, 0, 0))),
                             bouche=ecran(cam, mw @ Vector((0, -0.28, 0.61))),
                             main_d=ecran(cam, mw @ Vector(pose["mains"][1][0])),
                             main_g=ecran(cam, mw @ Vector(pose["mains"][0][0])),
                             px_par_m=round(abs(ecran(cam, mw @ Vector((0, 0, 1)))[1] - ecran(cam, mw @ Vector((0, 0, 0)))[1]), 1))
            bpy.ops.object.select_all(action="DESELECT")
            for o in objs:
                o.select_set(True)
            bpy.ops.object.delete()
            for blk in (bpy.data.meshes, bpy.data.curves):
                for d in list(blk):
                    if d.users == 0:
                        blk.remove(d)
    chemin = os.path.join(sortie, f"meta_{plan}.json")
    with open(chemin, "w") as fh:
        json.dump(meta, fh, indent=1)


# ===================================================================== accessoires
def canard_bain():
    jaune = mat("canard_corps", "#ffd93b", 0.28, sss=0.15, coat=0.6)
    orange = mat("canard_bec", "#ff8a1f", 0.3, coat=0.5)
    sphere("corps", (0, 0.05, 0.0), (0.62, 0.5, 0.4), jaune)
    sphere("queue", (0.0, 0.5, 0.18), (0.18, 0.2, 0.2), jaune, rot=(-40, 0, 0))
    sphere("tete", (0, -0.2, 0.55), 0.36, jaune)
    for s_ in (-1, 1):
        sphere("aile", (s_ * 0.55, 0.12, 0.08), (0.12, 0.32, 0.2), jaune, rot=(0, s_ * 20, 0))
        x, y, z = surface((0, -0.2, 0.55), (0.36, 0.36, 0.36), s_ * 0.14, 0.64)
        B3.oeil(x, y + 0.02, z, 0.1, "normal", couleur_iris="#3b2a1a", peau="#ffd93b")
        x, y, z = surface((0, -0.2, 0.55), (0.36, 0.36, 0.36), s_ * 0.23, 0.48)
        sphere("joue", (x, y + 0.02, z), (0.06, 0.03, 0.04), mat("joue_c", "#ff9eb5", 0.6))
    x, y, z = surface((0, -0.2, 0.55), (0.36, 0.36, 0.36), 0, 0.5)
    sphere("bec_haut", (0, y - 0.1, z + 0.015), (0.17, 0.14, 0.05), orange)
    sphere("bec_bas", (0, y - 0.07, z - 0.04), (0.13, 0.1, 0.035), orange)
    # petit chapeau de marin bleu (signe distinctif)
    bleu = mat("chapeau_c", "#3f86e8", 0.35, coat=0.4)
    cylindre("chapeau", (0.05, -0.2, 0.9), 0.17, 0.09, bleu, biseau=0.03, rot=(0, 12, 0))
    cylindre("bord_ch", (0.04, -0.2, 0.86), 0.21, 0.03, mat("bord_ch", "#ffffff", 0.4), biseau=0.01, rot=(0, 12, 0))
    sphere("pompon", (0.07, -0.2, 0.97), 0.05, mat("pompon", "#ff5c8d", 0.5))
    return 2.0, 0.25


def miroir_main():
    rose = mat("cadre_m", "#ff8fb8", 0.25, coat=0.6)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.07, location=(0, 0, 0.25),
                                     rotation=(math.pi / 2, 0, 0))
    t_ = bpy.context.object
    lisser(t_)
    t_.data.materials.append(rose)
    cylindre("vitre", (0, 0.01, 0.25), 0.5, 0.02, mat_degrade("vitre_m", "#f0fcff", "#b5e2ff", emission=0.3), rot=(90, 0, 0))
    cylindre("manche", (0, 0, -0.5), 0.07, 0.6, rose, biseau=0.03)
    sphere("bout", (0, 0, -0.82), 0.09, mat("bout_m", "#ffd23f", 0.3, coat=0.5))
    for k in range(8):
        a = k / 8 * 2 * math.pi
        sphere("perle_m", (0.58 * math.cos(a), -0.05, 0.25 + 0.58 * math.sin(a)), 0.05, mat("perle_m", "#ffd23f", 0.3, coat=0.6), seg=16)
    return 2.0, 0.0


ACCESSOIRES = {"canard": canard_bain, "miroir": miroir_main}


def rendre_accessoires(sortie, qualite):
    os.makedirs(sortie, exist_ok=True)
    meta = {}
    for nom, f in ACCESSOIRES.items():
        B3.vider()
        B3.reglages(600, 600, qualite)
        B3.monde("#dcefff", "#fff4e6", 0.7)
        B3.eclairage_studio()
        echelle, cz = f()
        cam = bpy.data.cameras.new("cam")
        cam.type = "ORTHO"
        cam.ortho_scale = echelle
        o = bpy.data.objects.new("cam", cam)
        bpy.context.collection.objects.link(o)
        o.location = (0, -20, cz)
        o.rotation_euler = (math.pi / 2, 0, 0)
        bpy.context.scene.camera = o
        B3.rendre(os.path.join(sortie, f"{nom}.png"))
        meta[nom] = dict(echelle=echelle, centre_z=cz)
    with open(os.path.join(sortie, "accessoires.json"), "w") as fh:
        json.dump(meta, fh, indent=1)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    sortie, quoi = argv[0], argv[1]
    qualite = int(argv[2]) if len(argv) > 2 else 48
    if quoi == "plans":
        rendre_plans(sortie, qualite)
    elif quoi.startswith("plan:"):
        rendre_plans(sortie, qualite, seulement=quoi[5:].split(","))
    elif quoi.startswith("garcon:"):
        plan, *reste = quoi[7:].split("/")
        rendre_garcon(sortie, qualite, plan, seulement=reste[0].split(",") if reste else None)
    elif quoi == "accessoires":
        rendre_accessoires(sortie, qualite)

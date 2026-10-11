"""Rendu des images (cairo + Pillow) et encodage vidéo avec ffmpeg.

- décor animé de la section (decors.py) + personnages SVG qui rebondissent en rythme ;
- transition « bulle » (cercle qui s'ouvre) à chaque changement de section ;
- karaoké : chaque mot passe du blanc à une couleur vive quand il est chanté,
  avec un petit rebond du mot actif ;
- rendu parallèle par morceaux, puis concaténation et ajout de l'audio.
"""
import math
import os
import random
import subprocess
from functools import lru_cache
from multiprocessing import Pool

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config as C
from . import decors as D
from . import fonds3d as F3
from .chanson import SECTIONS, TITRE

W, H = C.LARGEUR, C.HAUTEUR
TRANSITION = 0.6

# état global des processus de rendu (initialisé par init_worker)
G = {}

ANIMAL_MOTS = {
    "meuh": "vache", "vache": "vache", "coin": "canard", "canard": "canard",
    "groin": "cochon", "cochon": "cochon", "bê": "mouton", "mouton": "mouton",
    "cocorico": "coq", "coq": "coq", "cheval": "cheval", "hop": "cheval",
    "poussins": "poussin", "piou": "poussin",
}
RANGEE = ["coq", "vache", "canard", "cochon", "mouton", "cheval", "poussin"]


# ======================================================================= données
def preparer_donnees(lignes):
    """Transforme les lignes en structures simples (picklables) pour le rendu."""
    mots, syllabes, lignes_aff = [], [], []
    idx_global = 0
    for i, L in enumerate(lignes):
        lm = []
        for m in L.mots:
            cle = m.texte.lower()
            animal = next((a for k, a in ANIMAL_MOTS.items() if k in cle), None)
            d = dict(texte=m.texte, debut=m.debut, fin=m.fin, couleur=C.PALETTE[idx_global % len(C.PALETTE)],
                     animal=animal)
            idx_global += 1
            lm.append(d)
            mots.append(d)
        txt = L.texte.lower()
        chanteurs = sorted({a for k, a in ANIMAL_MOTS.items() if k in txt and k not in ("meuh", "coin", "groin", "bê", "hop", "piou")})
        lignes_aff.append(dict(texte=L.texte, mots=lm, section=L.section, type=L.type_section,
                               debut=lm[0]["debut"], fin=lm[-1]["fin"], chanteurs=chanteurs))
        for s in L.syllabes:
            syllabes.append((s.debut, s.fin, i))
    # fenêtres d'affichage des lignes (apparition un peu avant, disparition un peu après)
    for i, la in enumerate(lignes_aff):
        prec_fin = lignes_aff[i - 1]["fin"] if i else -1
        suiv_deb = lignes_aff[i + 1]["debut"] if i + 1 < len(lignes_aff) else 1e9
        la["aff_debut"] = max(la["debut"] - 0.7, prec_fin + 0.15) if i else la["debut"] - 0.7
        la["aff_fin"] = min(la["fin"] + 0.8, max(la["fin"] + 0.05, suiv_deb - 0.7))
        if i + 1 < len(lignes_aff):
            la["aff_fin"] = min(la["aff_fin"], max(la["fin"], suiv_deb - 0.7))
    return dict(mots=mots, syllabes=syllabes, lignes=lignes_aff)


def init_worker(donnees, echelle):
    G["d"] = donnees
    G["echelle"] = echelle
    G["3d"] = F3.charger()


@lru_cache(maxsize=256)
def police(taille):
    f = ImageFont.truetype(str(C.POLICE), max(8, int(taille)))
    try:
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    return f


# ======================================================================= temps
def section_index(t):
    m = t / C.MESURE
    idx = 0
    for k, s in enumerate(SECTIONS):
        if m >= s[2] - 1e-9:
            idx = k
    return idx


def syllabe_active(t):
    for deb, fin, li in G["d"]["syllabes"]:
        if deb - 0.04 <= t < fin:
            return deb, fin, li
    return None


def pop_animal(animal, t):
    """0..1 : l'animal « saute » quand on chante son cri ou son nom."""
    best = 0.0
    for m in G["d"]["mots"]:
        if m["animal"] == animal and m["debut"] - 0.05 <= t <= m["debut"] + 0.5:
            u = (t - m["debut"] + 0.05) / 0.55
            best = max(best, math.sin(math.pi * min(1, max(0, u))))
    return best


def bouche_ouverte(animal, t, chanteurs_section):
    sa = syllabe_active(t)
    if not sa:
        return False
    deb, fin, li = sa
    ligne = G["d"]["lignes"][li]
    chanteurs = ligne["chanteurs"] or chanteurs_section
    if animal not in chanteurs:
        return False
    return (t - deb) < 0.78 * (fin - deb)


def cligne(animal, t):
    rnd = random.Random(sum(map(ord, animal)))
    periode = rnd.uniform(2.8, 4.2)
    ph = (t + rnd.uniform(0, 3)) % periode
    return ph < 0.13


# ======================================================================= personnages
def dessiner_perso(ctx, nom, x, y, taille, t, phase=0.0, ampl=20.0, chante=False,
                   dort=False, rot=0.0, flip=False, saut=0.0, freq=1.0):
    """Personnage 3D (sprite Blender). `taille` = nombre de pixels pour 3 m."""
    g3 = G["3d"]
    ph = ((t / C.NOIRE) * freq + phase) % 1.0
    h = ampl * math.sin(math.pi * ph) + saut * 90
    ecrase = (0.10 * math.exp(-ph * 9) if ampl > 2 else 0.0)
    sx = 1 + ecrase + 0.10 * saut
    sy = 1 - ecrase + 0.05 * math.sin(math.pi * ph) * min(1, ampl / 40) + 0.10 * saut
    if dort:
        sy = 1 + 0.025 * math.sin(t * 1.6)
        sx = 1 + 0.015 * math.sin(t * 1.6 + 1)
    # ombre douce au sol
    ombre = max(0.35, 1 - h / 260)
    g = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
    g.add_color_stop_rgba(0, 0.1, 0.12, 0.2, 0.32)
    g.add_color_stop_rgba(1, 0.1, 0.12, 0.2, 0.0)
    ctx.save()
    ctx.translate(x, y + 2)
    ctx.scale(taille * 0.3 * ombre, taille * 0.055 * ombre)
    ctx.arc(0, 0, 1, 0, 2 * math.pi)
    ctx.set_source(g)
    ctx.fill()
    ctx.restore()

    if dort or cligne(nom, t):
        etat = "cligne"
    elif chante:
        etat = "chante"
    else:
        etat = "normal"
    surf = g3["persos"][(nom, etat)]
    meta = g3["meta"][nom]
    k = taille / 3.0 / meta["px_par_m"]
    ax, ay = meta["ancre"]
    ctx.save()
    ctx.translate(x, y - h)
    ctx.rotate(rot)
    ctx.scale(k * sx * (-1 if flip else 1), k * sy)
    ctx.set_source_surface(surf, -surf.get_width() * ax, -surf.get_height() * ay)
    ctx.get_source().set_filter(cairo.FILTER_GOOD)
    ctx.paint()
    ctx.restore()


def zzz(ctx, x, y, t):
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    for k in range(3):
        ph = (t * 0.35 + k / 3) % 1
        ctx.set_font_size(30 + 40 * ph)
        ctx.move_to(x + 60 * ph + 20 * math.sin(ph * 8), y - 220 * ph)
        ctx.set_source_rgba(0.85, 0.85, 1.0, math.sin(math.pi * ph))
        ctx.show_text("z")


def distribution(decor, t, tl, typ):
    """Liste des personnages à dessiner pour un décor : dicts de paramètres.
    `taille` = pixels pour 3 m (la vache mesure ~2,9 m, le poussin ~1,5 m)."""
    if decor == "aube":
        return [dict(nom="poussin", x=1580, y=855, taille=400, phase=0.5, ampl=14),
                dict(nom="coq", x=1250, y=840, taille=520, ampl=16)], ["coq"]
    if decor == "pre":
        return [dict(nom="coq", x=560, y=840, taille=520, ampl=18),
                dict(nom="vache", x=1280, y=850, taille=560, phase=0.5, ampl=14)], ["coq", "vache"]
    if decor == "mare":
        bob = 8 * math.sin(t * 2.2)
        return [dict(nom="canard", x=680 + 110 * math.sin(tl * 0.35), y=812 + bob, taille=460, ampl=5,
                     rot=0.05 * math.sin(t * 2.2), flip=math.cos(tl * 0.35) < 0),
                dict(nom="cochon", x=1470, y=795, taille=520, phase=0.5, ampl=18)], ["canard", "cochon"]
    if decor == "nuit":
        return [dict(nom="mouton", x=980, y=845, taille=540, ampl=0, dort=True)], []
    if decor == "foret":
        duree = 8 * C.MESURE
        u = 0.5 - 0.5 * math.cos(2 * math.pi * tl / duree)
        vit = math.sin(2 * math.pi * tl / duree)
        res = [dict(nom="coq", x=230, y=855, taille=430, ampl=16),
               dict(nom="cheval", x=560 + 900 * u, y=840, taille=520, ampl=24, freq=2.0, flip=vit < 0)]
        for k in range(3):
            tk = max(0.0, tl - 0.9 * (k + 1))
            uk = 0.5 - 0.5 * math.cos(2 * math.pi * tk / duree)
            res.append(dict(nom="poussin", x=560 + 900 * uk - (210 + 130 * k) * (1 if vit >= 0 else -1),
                            y=860, taille=360, ampl=22, phase=0.25 * k, freq=2.0))
        return res, ["coq", "cheval", "poussin"]
    # rangée de tous les animaux : grange, fête, couchant
    res = []
    n = len(RANGEE)
    for k, nom in enumerate(RANGEE):
        x = 170 + k * (W - 340) / (n - 1)
        p = dict(nom=nom, x=x, y=840 - 12 * (k % 2), taille=400 if nom != "poussin" else 380,
                 phase=0.5 * (k % 2))
        if decor == "grange":
            p.update(ampl=32)
        elif decor == "fete":
            p.update(ampl=46, rot=0.12 * math.sin(2 * math.pi * t / (2 * C.NOIRE) + k))
        else:
            p.update(ampl=12, rot=0.15 * math.sin(2 * math.pi * t / (2 * C.NOIRE) + k * 0.6))
        res.append(p)
    return res, list(RANGEE)


def dessiner_scene(ctx, idx, t):
    nom, typ, m0, nb, decor, tr = SECTIONS[idx]
    tl = t - m0 * C.MESURE
    F3.arriere_plan(ctx, decor, t, tl, tr)
    ctx.save()
    F3.camera(ctx, decor, tl, nb * C.MESURE)
    F3.decor(ctx, decor)
    persos, chanteurs = distribution(decor, t, tl, typ)
    for p in sorted(persos, key=lambda p: p["y"]):
        chante = bouche_ouverte(p["nom"], t, chanteurs)
        saut = pop_animal(p["nom"], t)
        dessiner_perso(ctx, t=t, chante=chante, saut=saut, **p)
    if decor == "nuit":
        zzz(ctx, 1110, 520, t)
    ctx.restore()
    F3.premier_plan(ctx, decor, t, tl, tr)


def dessiner_monde(ctx, t):
    idx = section_index(t)
    debut = SECTIONS[idx][2] * C.MESURE
    if idx > 0 and t - debut < TRANSITION:
        u = (t - debut) / TRANSITION
        u = u * u * (3 - 2 * u)
        dessiner_scene(ctx, idx - 1, t)
        r = u * math.hypot(W / 2, H / 2) * 1.05
        ctx.save()
        ctx.arc(W / 2, H / 2, max(r, 0.1), 0, 2 * math.pi)
        ctx.clip()
        dessiner_scene(ctx, idx, t)
        ctx.restore()
        ctx.set_source_rgba(1, 1, 1, 0.9)
        ctx.set_line_width(26 * (1 - u) + 4)
        ctx.arc(W / 2, H / 2, max(r, 0.1), 0, 2 * math.pi)
        ctx.stroke()
    else:
        dessiner_scene(ctx, idx, t)


# ======================================================================= textes
CONTOUR = (58, 28, 92)


def texte_contour(draw, xy, txt, taille, couleur, ancre="ms", ep=None):
    e = G["echelle"]
    f = police(taille * e)
    ep = int(round((ep or max(4, taille * 0.11)) * e))
    x, y = xy[0] * e, xy[1] * e
    # ombre portée
    draw.text((x + 5 * e, y + 7 * e), txt, font=f, fill=(40, 20, 70), anchor=ancre,
              stroke_width=ep, stroke_fill=(40, 20, 70))
    draw.text((x, y), txt, font=f, fill=couleur, anchor=ancre, stroke_width=ep, stroke_fill=CONTOUR)


def largeur(txt, taille):
    return police(taille).getlength(txt)


def dessiner_karaoke(draw, t):
    ligne = None
    for la in G["d"]["lignes"]:
        if la["aff_debut"] <= t < la["aff_fin"]:
            ligne = la
            break
    if not ligne:
        return
    app = min(1.0, (t - ligne["aff_debut"]) / 0.15)
    taille = 86 * (0.6 + 0.4 * app)
    espace = largeur(" ", taille) * 1.1
    mots = ligne["mots"]
    total = sum(largeur(m["texte"], taille) for m in mots) + espace * (len(mots) - 1)
    if total > W - 160:
        taille = taille * (W - 160) / total
        espace = largeur(" ", taille) * 1.1
        total = sum(largeur(m["texte"], taille) for m in mots) + espace * (len(mots) - 1)
    y = 1010 + 30 * (1 - app)
    x = (W - total) / 2
    for m in mots:
        wm = largeur(m["texte"], taille)
        cx = x + wm / 2
        if t < m["debut"]:
            couleur, echelle, dy = (255, 255, 255), 1.0, 0.0
        else:
            couleur = m["couleur"]
            u = (t - m["debut"]) / 0.32
            pop = math.sin(math.pi * min(1.0, u)) if u < 1 else 0.0
            actif = t < m["fin"]
            echelle = 1 + 0.11 * pop + (0.03 if actif else 0.0)
            dy = -16 * pop - (5 if actif else 0)
        texte_contour(draw, (cx, y + dy), m["texte"].replace(" ", " "), taille * echelle, couleur)
        x += wm + espace


def dessiner_titres(draw, t):
    # titre de l'intro, lettre par lettre, couleurs de la palette
    if t < 7.4:
        apparition = min(1.0, t / 0.6)
        disparition = min(1.0, max(0.0, (7.4 - t) / 0.5))
        taille = 150 * apparition * disparition
        if taille > 4:
            lettres = list(TITRE)
            larg = [largeur(c, 150) for c in lettres]
            x = (W - sum(larg)) / 2
            for k, (c, wl) in enumerate(zip(lettres, larg)):
                if c != " ":
                    ph = (t / C.NOIRE - k * 0.12) % 1
                    dy = -26 * abs(math.sin(math.pi * ph))
                    texte_contour(draw, (x + wl / 2, 330 + dy), c, taille, C.PALETTE[k % len(C.PALETTE)], ep=16)
                x += wl
    # « À bientôt ! » à la toute fin
    fin = C.DUREE_TOTALE
    if t > fin - 2.2:
        u = min(1.0, (t - (fin - 2.2)) / 0.4)
        pop = 1 + 0.15 * math.sin(math.pi * min(1, u))
        texte_contour(draw, (W / 2, 420), "À bientôt !", 170 * u * pop, C.PALETTE[(int(t * 4)) % 7], ep=18)


# ======================================================================= image
def rendre_image(t):
    e = G["echelle"]
    w, h = int(W * e), int(H * e)
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    ctx = cairo.Context(surf)
    ctx.scale(e, e)
    dessiner_monde(ctx, t)
    surf.flush()
    a = np.ndarray((h, surf.get_stride() // 4, 4), np.uint8, surf.get_data())[:, :w, 2::-1]
    img = Image.fromarray(np.ascontiguousarray(a), "RGB")
    draw = ImageDraw.Draw(img)
    dessiner_titres(draw, t)
    dessiner_karaoke(draw, t)
    return img


def rendre_morceau(args):
    i0, i1, chemin, image = args
    image = image or rendre_image
    e = G["echelle"]
    w, h = int(W * e), int(H * e)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(C.FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "19",
           "-pix_fmt", "yuv420p", "-threads", "2", str(chemin)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(i0, i1):
        p.stdin.write(image(i / C.FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg a échoué pour {chemin}")
    return i1 - i0


def rendre_video(lignes, audio, sortie, dossier_tmp, echelle=1.0, processus=None, debut=0.0, fin=None,
                 init=None, image=None):
    """Rend toutes les images en parallèle puis assemble la vidéo finale avec l'audio.

    `init` / `image` : initialisation des processus et rendu d'une image (par défaut ceux
    de « Bonjour la ferme ! ») — fonctions de module, transmises aux processus."""
    donnees = preparer_donnees(lignes)
    fin = C.DUREE_TOTALE if fin is None else fin
    i_deb, i_fin = int(round(debut * C.FPS)), int(math.ceil(fin * C.FPS))
    processus = processus or max(1, (os.cpu_count() or 2))
    n_morceaux = processus * 3
    bornes = np.linspace(i_deb, i_fin, n_morceaux + 1).astype(int)
    taches = [(int(a), int(b), dossier_tmp / f"morceau_{k:03d}.mp4", image)
              for k, (a, b) in enumerate(zip(bornes[:-1], bornes[1:])) if b > a]
    total = i_fin - i_deb
    fait = 0
    with Pool(processus, initializer=init or init_worker, initargs=(donnees, echelle)) as pool:
        for n in pool.imap_unordered(rendre_morceau, taches):
            fait += n
            print(f"\r   images : {fait}/{total} ({100 * fait / total:.0f} %)", end="", flush=True)
    print()
    liste = dossier_tmp / "morceaux.txt"
    liste.write_text("".join(f"file '{c.resolve()}'\n" for _, _, c, _ in taches))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(liste),
                    "-ss", f"{debut:.3f}", "-t", f"{fin - debut:.3f}", "-i", str(audio),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", str(sortie)], check=True)
    for _, _, c, _ in taches:
        c.unlink(missing_ok=True)
    liste.unlink(missing_ok=True)


def apercu(lignes, temps, chemin, echelle=0.5):
    """Image fixe à l'instant `temps` (pour vérifier rapidement le rendu)."""
    init_worker(preparer_donnees(lignes), echelle)
    rendre_image(temps).save(chemin)

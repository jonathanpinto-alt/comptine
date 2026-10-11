"""Écrit les SVG (assets/toc/svg) et les rastérise (assets/toc/png) avec cairosvg.

Chaque pièce de personnage est rastérisée dans le cadre complet (600 x 720, ×ECHELLE),
puis recadrée ; le décalage, le pivot, le parent et l'ordre sont notés dans rig.json.
"""
import io
import json

import cairosvg
from PIL import Image

from .. import config as C
from . import decors_svg, svg as S

DOSSIER = C.ASSETS / "toc"
ECHELLE = 1.0          # 600 x 720 → personnage d'environ 700 px de haut


def rasteriser(code_svg, echelle=1.0):
    png = cairosvg.svg2png(bytestring=code_svg.encode("utf-8"), scale=echelle)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def generer(forcer=False):
    rig_chemin = DOSSIER / "png" / "rig.json"
    if rig_chemin.exists() and not forcer:
        return
    (DOSSIER / "svg").mkdir(parents=True, exist_ok=True)
    (DOSSIER / "png").mkdir(parents=True, exist_ok=True)
    rig = {}
    for nom, f in S.PERSONNAGES.items():
        pieces = f()
        rig[nom] = {}
        complet = ""
        for piece, d in sorted(pieces.items(), key=lambda kv: kv[1]["z"]):
            code = S.svg(d["svg"])
            (DOSSIER / "svg" / f"{nom}_{piece}.svg").write_text(code, encoding="utf-8")
            if piece not in ("yeux_fermes", "bouche_ouverte"):
                complet += d["svg"]
            im = rasteriser(code, ECHELLE)
            boite = im.getchannel("A").getbbox() or (0, 0, 1, 1)
            im.crop(boite).save(DOSSIER / "png" / f"{nom}_{piece}.png")
            rig[nom][piece] = dict(decalage=[boite[0], boite[1]], pivot=[v * ECHELLE for v in d["pivot"]],
                                   parent=d["parent"], z=d["z"])
        (DOSSIER / "svg" / f"{nom}.svg").write_text(S.svg(complet), encoding="utf-8")
    for nom, f in S.ACCESSOIRES.items():
        code = f()
        (DOSSIER / "svg" / f"{nom}.svg").write_text(code, encoding="utf-8")
        rasteriser(code).save(DOSSIER / "png" / f"{nom}.png")
    for nom, couches in decors_svg.DECORS.items():
        for couche, f in couches.items():
            code = f()
            (DOSSIER / "svg" / f"decor_{nom}_{couche}.svg").write_text(code, encoding="utf-8")
            rasteriser(code).save(DOSSIER / "png" / f"decor_{nom}_{couche}.png")
    rig_chemin.write_text(json.dumps(rig, indent=1))

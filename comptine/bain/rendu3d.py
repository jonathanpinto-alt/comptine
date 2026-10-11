"""Lance Blender (en arrière-plan) pour les rendus 3D du bain, puis recadre les sprites.

Rendus mis en cache dans assets/bain/rendus3d/ (refaits s'ils manquent, ou avec
`python main.py --chanson bain --refaire-3d`). Les sprites du garçon sont rendus
plein cadre (1920x1080) puis recadrés sur leur contenu ; le décalage est noté
dans decoupes.json.
"""
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from .. import config as C

SCRIPT = C.RACINE / "comptine" / "bain" / "blender_bain.py"
DOSSIER = C.ASSETS / "bain" / "rendus3d"
TACHES = ["plans", "garcon:large", "garcon:bain", "garcon:proche", "garcon:lavabo", "accessoires"]


def dossier_tache(tache):
    return DOSSIER / {"plans": "plans", "accessoires": "accessoires"}.get(tache, "garcon")


def complet():
    return (DOSSIER / "garcon" / "decoupes.json").exists() and (DOSSIER / "plans" / "plans.json").exists() \
        and (DOSSIER / "accessoires" / "accessoires.json").exists() \
        and all((DOSSIER / "garcon" / f"meta_{p}.json").exists() for p in ("large", "bain", "proche", "lavabo"))


def lancer(tache, qualite):
    dossier = dossier_tache(tache)
    dossier.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["blender", "-b", "--factory-startup", "-P", str(SCRIPT), "--", str(dossier), tache,
                        str(qualite)], capture_output=True, text=True)
    if r.returncode != 0 or "Traceback" in r.stdout + r.stderr:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"échec du rendu Blender ({tache})")
    print(f"   ✓ {tache}", flush=True)


def recadrer(dossier):
    """Recadre chaque sprite plein cadre sur sa zone non transparente."""
    chemin = dossier / "decoupes.json"
    decoupes = json.loads(chemin.read_text()) if chemin.exists() else {}
    for f in sorted(dossier.glob("*__*.png")):
        im = Image.open(f)
        if im.size != (C.LARGEUR, C.HAUTEUR) and f.name in decoupes:
            continue
        boite = im.getchannel("A").point(lambda a: 255 if a > 2 else 0).getbbox() or (0, 0, 1, 1)
        x0, y0, x1, y1 = boite
        x0, y0 = max(0, x0 - 2), max(0, y0 - 2)
        x1, y1 = min(im.width, x1 + 2), min(im.height, y1 + 2)
        im.crop((x0, y0, x1, y1)).save(f)
        decoupes[f.name] = [x0, y0]
    chemin.write_text(json.dumps(decoupes, indent=1))


def rendre(qualite=48, forcer=False):
    if complet() and not forcer:
        print("   rendus 3D déjà présents (assets/bain/rendus3d) — --refaire-3d pour les refaire")
        return
    if not shutil.which("blender"):
        raise SystemExit("Blender est nécessaire pour les rendus 3D (apt install blender)")
    if forcer:
        shutil.rmtree(DOSSIER, ignore_errors=True)
    print(f"   Blender : {len(TACHES)} tâches (2 en parallèle, environ 25 min)…", flush=True)
    with ThreadPoolExecutor(2) as ex:
        list(ex.map(lambda t: lancer(t, qualite), TACHES))
    recadrer(DOSSIER / "garcon")

"""Lance Blender (en arrière-plan) pour modéliser et rendre les éléments 3D.

Les rendus sont mis en cache dans assets/rendus3d/ : ils ne sont refaits que
s'ils manquent (ou avec `python main.py --refaire-3d`).
"""
import shutil
import subprocess

from . import config as C

SCRIPT = C.RACINE / "comptine" / "blender3d.py"
DOSSIER = C.ASSETS / "rendus3d"
TACHES = {"persos": 21, "decors": 8, "accessoires": 13}


def complet():
    return all((DOSSIER / t).exists() and len(list((DOSSIER / t).glob("*.png"))) >= n for t, n in TACHES.items())


def rendre(qualite=64, forcer=False):
    if complet() and not forcer:
        print("   rendus 3D déjà présents (assets/rendus3d) — utiliser --refaire-3d pour les refaire")
        return
    if not shutil.which("blender"):
        raise SystemExit("Blender est nécessaire pour les rendus 3D (apt install blender)")
    for tache in TACHES:
        print(f"   Blender : {tache}…", flush=True)
        dossier = DOSSIER / tache
        dossier.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["blender", "-b", "--factory-startup", "-P", str(SCRIPT), "--", str(dossier), tache,
                            str(qualite)], capture_output=True, text=True)
        if r.returncode != 0 or "Traceback" in r.stdout + r.stderr:
            print(r.stdout[-3000:], r.stderr[-3000:])
            raise SystemExit(f"échec du rendu Blender ({tache})")

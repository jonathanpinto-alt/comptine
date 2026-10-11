"""Chaîne complète de « Toc toc toc, qui est là ? » (appelée par main.py --chanson toc)."""
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .. import config as C


def etape(msg):
    print(f"\n▶ {msg}", flush=True)


def police_systeme():
    """Rend la police Fredoka visible de cairo (bulles « TOC ! ») via fontconfig."""
    dest = Path.home() / ".local" / "share" / "fonts" / "Fredoka.ttf"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(C.POLICE, dest)
        subprocess.run(["fc-cache", "-f", str(dest.parent)], capture_output=True)


def lancer(args):
    from . import son as S
    if not (S.AUDIO.exists() and S.ALIGNEMENT.exists()):
        sys.exit(f"Chanson absente ({S.AUDIO}) ou non calée : python outils/aligner_son.py --chanson toc")
    from main import duree_media
    duree = duree_media(S.AUDIO)
    C.configurer(S.BPM, duree / (4 * 60.0 / S.BPM), duree - 1.0, duree + 1.0, sortie=C.RACINE / "sortie" / "toc")
    from .. import soustitres
    from . import actifs, chanson as T, rendu

    C.SORTIE.mkdir(parents=True, exist_ok=True)
    C.TMP.mkdir(exist_ok=True)
    police_systeme()
    t0 = time.time()

    etape(f"Chanson fournie : {S.AUDIO.name} ({duree:.2f} s)")
    lignes = S.construire_lignes()
    print(f"   {len(lignes)} lignes chantées calées, {sum(len(L.mots) for L in lignes)} mots")

    etape("Dessins SVG → PNG (personnages riggés, décors en couches, accessoires)")
    actifs.generer(forcer=args.refaire_3d)

    donnees = rendu.preparer_donnees(lignes)
    donnees["plans"] = S.plans(lignes, duree)
    donnees["phase"] = S.PHASE
    if args.apercu is not None:
        chemin = C.SORTIE / f"apercu_{args.apercu:.1f}s.png"
        rendu.init_worker(donnees, 1.0)
        rendu.rendre_image(args.apercu).save(chemin)
        print(f"   → {chemin}")
        return

    etape("Audio : la chanson fournie, sans modification")
    audio = C.SORTIE / "audio_final.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(S.AUDIO), "-map", "0:a", "-ar", str(C.SR), "-ac", "2",
                    str(audio)], check=True)

    etape("Sous-titres (paroles.json avec qui chante, .srt, .ass)")
    plans = [dict(debut=round(a, 3), fin=round(b, 3), decor=d, section=s_) for a, b, d, s_, _n in donnees["plans"]]
    soustitres.ecrire_json(donnees, C.SORTIE / "paroles.json", duree, 1.0, titre=T.TITRE, sections=[],
                           extra=dict(audio=S.AUDIO.name, plans=plans))
    ajouter_chanteurs(C.SORTIE / "paroles.json", lignes, T)
    soustitres.ecrire_srt(donnees, C.SORTIE / "video_finale.srt")
    soustitres.ecrire_ass(donnees, C.SORTIE / "video_finale.ass", titre=T.TITRE)

    etape("Miniature YouTube 1920x1080")
    rendu.miniature(C.SORTIE / "miniature.png")
    print(f"   → {C.SORTIE / 'miniature.png'}")
    if args.audio_seulement:
        return

    etape("Rendu vidéo" + (" (rapide 960x540)" if args.rapide else " 1920x1080 30 fps"))
    video = C.SORTIE / ("video_essai.mp4" if args.rapide else "video_finale.mp4")
    rendu.rendre_video(lignes, audio, video, C.TMP, echelle=0.5 if args.rapide else 1.0, processus=args.processus,
                       donnees=donnees)
    dv = duree_media(video)
    print(f"\n✓ Vidéo : {video}")
    print(f"  durée : {dv:.2f} s ({int(dv // 60)} min {dv % 60:04.1f} s) — audio {duree:.2f} s")
    print(f"  temps total : {(time.time() - t0) / 60:.1f} min")


def ajouter_chanteurs(chemin, lignes, T):
    """Ajoute à paroles.json, pour chaque ligne et chaque mot, qui chante (solo/chœur, voix, personnage)."""
    import json
    doc = json.loads(chemin.read_text(encoding="utf-8"))
    for el, L in zip(doc["lignes"], lignes):
        qui = T.voix_des_mots(L)
        voix = {v for v, _p in qui}
        el["chante"] = "choeur" if voix == {"choeur"} else ("solo" if len(voix) == 1 else "solo + réponse")
        el["voix"] = sorted(voix)
        for m, (v, p) in zip(el["mots"], qui):
            m["voix"], m["personnage"] = v, p
    chemin.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

#!/usr/bin/env python3
"""Génère une comptine vidéo complète : « Bonjour la ferme ! » ou « C'est l'heure du bain ».

    python main.py                 # tout : audio, sous-titres, vidéo 1920x1080 30 fps (la ferme)
    python main.py --chanson bain  # « C'est l'heure du bain » (3 min) → sortie/bain/
    python main.py --rapide        # vidéo d'essai en 960x540
    python main.py --audio-seulement
    python main.py --apercu 30     # une image PNG à t = 30 s
    python main.py --voix mbrola   # ancienne voix de synthèse (sans modèle neuronal)
    python main.py --refaire-3d    # refait les rendus Blender (sinon mis en cache)
"""
import argparse
import json
import shutil
import subprocess
import sys
import time

import soundfile as sf

from comptine import config as C


def verifier_programmes():
    manquants = [p for p in ("ffmpeg", "ffprobe", "fluidsynth", "espeak-ng", "mbrola", "blender")
                 if not shutil.which(p)]
    if manquants:
        sys.exit("Programmes manquants : " + ", ".join(manquants) + "\n→ voir README.md (apt install …)")


def duree_media(chemin):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", str(chemin)], capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def recaler(lignes, ratio):
    """Applique la durée réelle de l'audio aux timings (ratio ≈ 1)."""
    for L in lignes:
        for s in L.syllabes:
            s.debut *= ratio
            s.fin *= ratio
        for m in L.mots:
            m.debut *= ratio
            m.fin *= ratio


def etape(msg):
    print(f"\n▶ {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chanson", choices=["ferme", "bain"], default="ferme",
                    help="ferme : « Bonjour la ferme ! » ; bain : « C'est l'heure du bain » (sortie/bain/)")
    ap.add_argument("--rapide", action="store_true", help="rendu 960x540 (essai)")
    ap.add_argument("--son", choices=["fourni", "synthese"], default="fourni",
                    help="bain : chanson fournie (assets/bain/son/chanson.mp3, défaut) ou voix et musique synthétisées")
    ap.add_argument("--audio-seulement", action="store_true")
    ap.add_argument("--apercu", type=float, metavar="T", help="écrit une image PNG à l'instant T")
    ap.add_argument("--processus", type=int, default=None, help="nombre de processus de rendu")
    ap.add_argument("--voix", choices=["kokoro", "mbrola"], default="kokoro",
                    help="kokoro : voix neuronale qui chante (défaut) ; mbrola : synthèse classique")
    ap.add_argument("--refaire-3d", action="store_true", help="refaire les rendus 3D Blender")
    ap.add_argument("--qualite-3d", type=int, default=64, help="échantillons Eevee des rendus 3D")
    args = ap.parse_args()

    verifier_programmes()
    if args.chanson == "bain":
        from comptine.bain import principal
        return principal.lancer(args)
    from comptine import mixage, musique, rendu, rendu3d, soustitres, voix

    C.SORTIE.mkdir(exist_ok=True)
    C.TMP.mkdir(exist_ok=True)
    t0 = time.time()

    etape("Paroles → syllabes, rythme et mélodie")
    lignes = voix.preparer_lignes()
    print(f"   {len(lignes)} lignes, {sum(len(L.mots) for L in lignes)} mots, "
          f"{sum(len(L.syllabes) for L in lignes)} syllabes chantées")

    etape("Modèles 3D (Blender) : personnages, décors, accessoires")
    rendu3d.rendre(args.qualite_3d, forcer=args.refaire_3d)

    if args.apercu is not None:
        chemin = C.SORTIE / f"apercu_{args.apercu:.1f}s.png"
        rendu.apercu(lignes, args.apercu, chemin, echelle=1.0)
        print(f"   → {chemin}")
        return

    if args.voix == "kokoro":
        from comptine import voix_kokoro
        etape("Voix chantée (Kokoro qui chante + WORLD, timbre enfantin, chœur)")
        v = voix_kokoro.synthetiser(lignes, C.TMP)
    else:
        etape("Voix chantée (espeak-ng + MBROLA)")
        v = voix.synthetiser(lignes, C.TMP)

    etape("Musique (MIDI → FluidSynth)")
    pm = musique.composer(lignes)
    m = musique.rendre(pm, C.TMP)
    shutil.copy(C.TMP / "musique.mid", C.SORTIE / "musique.mid")

    etape("Mixage (voix devant, musique à -8 dB)")
    audio = C.SORTIE / "audio_final.wav"
    duree, gain = mixage.mixer(v, m, audio)
    print(f"   gain musique : {gain:+.1f} dB → {audio}")
    print(f"   durée audio : {duree:.2f} s ({int(duree // 60)} min {duree % 60:04.1f} s)")
    if not C.DUREE_MIN <= duree <= C.DUREE_MAX:
        sys.exit(f"✗ durée hors cible ({C.DUREE_MIN}–{C.DUREE_MAX} s)")
    print("   ✓ durée dans la cible 2 min 25 – 2 min 35")

    etape("Sous-titres (paroles.json, .srt, .ass)")
    duree_reelle = len(sf.read(audio)[0]) / C.SR
    ratio = duree_reelle / C.DUREE_TOTALE
    recaler(lignes, ratio)
    donnees = rendu.preparer_donnees(lignes)
    soustitres.ecrire_json(donnees, C.SORTIE / "paroles.json", duree_reelle, ratio)
    soustitres.ecrire_srt(donnees, C.SORTIE / "video_finale.srt")
    soustitres.ecrire_ass(donnees, C.SORTIE / "video_finale.ass")
    print(f"   recalage sur l'audio réel : ratio {ratio:.6f}")

    if args.audio_seulement:
        return

    etape("Rendu vidéo" + (" (rapide 960x540)" if args.rapide else " 1920x1080 30 fps"))
    video = C.SORTIE / ("video_essai.mp4" if args.rapide else "video_finale.mp4")
    rendu.rendre_video(lignes, audio, video, C.TMP, echelle=0.5 if args.rapide else 1.0,
                       processus=args.processus)

    dv = duree_media(video)
    print(f"\n✓ Vidéo : {video}")
    print(f"  durée : {dv:.2f} s ({int(dv // 60)} min {dv % 60:04.1f} s) — "
          + ("OK" if C.DUREE_MIN <= dv <= C.DUREE_MAX else "HORS CIBLE"))
    print(f"  temps total : {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

"""Chaîne complète de « C'est l'heure du bain » (appelée par main.py --chanson bain)."""
import shutil
import sys
import time

import numpy as np
import soundfile as sf

from .. import config as C
from . import chanson as B

VOIX_CHOEUR_BAIN = [   # trois voix d'enfants, réparties à gauche, à droite et au centre
    (1.24, +9, 0.016, 0.45, "g"),
    (1.30, -8, 0.027, 0.45, "d"),
    (1.18, +3, 0.038, 0.30, "g"),
]


def etape(msg):
    print(f"\n▶ {msg}", flush=True)


def lancer(args):
    C.configurer(B.BPM, B.NB_MESURES, B.DUREE_MIN, B.DUREE_MAX, sortie=C.RACINE / "sortie" / "bain")
    from .. import mixage, soustitres, voix
    from . import musique, rendu, rendu3d
    from main import duree_media, recaler

    C.SORTIE.mkdir(parents=True, exist_ok=True)
    C.TMP.mkdir(exist_ok=True)
    t0 = time.time()

    etape("Paroles → syllabes, rythme et mélodie")
    lignes = voix.preparer_lignes(B.construire_lignes)
    print(f"   {len(lignes)} lignes, {sum(len(L.mots) for L in lignes)} mots, "
          f"{sum(len(L.syllabes) for L in lignes)} syllabes chantées")

    if not args.audio_seulement:
        etape("Modèles 3D (Blender) : petit garçon, salle de bain, accessoires")
        rendu3d.rendre(args.qualite_3d, forcer=args.refaire_3d)

    if args.apercu is not None:
        chemin = C.SORTIE / f"apercu_{args.apercu:.1f}s.png"
        rendu.apercu(lignes, args.apercu, chemin, echelle=1.0)
        print(f"   → {chemin}")
        return

    if args.voix == "kokoro":
        from .. import voix_kokoro
        etape("Voix chantée (Kokoro qui chante + WORLD) : voix chaleureuse, chœur d'enfants aux refrains")
        v = voix_kokoro.synthetiser(lignes, C.TMP, choeur=("refrain",), alpha_lead=1.03,
                                    voix_choeur=VOIX_CHOEUR_BAIN)
    else:
        etape("Voix chantée (espeak-ng + MBROLA)")
        v = voix.synthetiser(lignes, C.TMP)

    etape("Musique (MIDI → FluidSynth) + bruitages (bulles, éclaboussures, canard)")
    from ..musique import rendre as rendre_midi
    pm = musique.composer(lignes)
    m = rendre_midi(pm, C.TMP)
    m = m + musique.bruitages(lignes, len(m)) * 0.6 * float(np.max(np.abs(m)))
    shutil.copy(C.TMP / "musique.mid", C.SORTIE / "musique.mid")

    etape("Mixage (voix devant, musique à -8 dB)")
    audio = C.SORTIE / "audio_final.wav"
    duree, gain = mixage.mixer(v, m, audio)
    print(f"   gain musique : {gain:+.1f} dB → {audio}")
    print(f"   durée audio : {duree:.2f} s ({int(duree // 60)} min {duree % 60:04.1f} s)")
    if not C.DUREE_MIN <= duree <= C.DUREE_MAX:
        sys.exit(f"✗ durée hors cible ({C.DUREE_MIN}–{C.DUREE_MAX} s)")
    print("   ✓ durée dans la cible (3 min)")

    etape("Sous-titres (paroles.json, .srt, .ass)")
    duree_reelle = len(sf.read(audio)[0]) / C.SR
    ratio = duree_reelle / C.DUREE_TOTALE
    recaler(lignes, ratio)
    donnees = rendu.preparer_donnees(lignes)
    plans = [dict(debut=round(a, 3), fin=round(b, 3), scene=s) for a, b, s, _k, _o in B.plan_de_montage(C.MESURE)]
    soustitres.ecrire_json(donnees, C.SORTIE / "paroles.json", duree_reelle, ratio, titre=B.TITRE,
                           sections=B.SECTIONS, cle_decor="scenes", extra=dict(plans=plans))
    soustitres.ecrire_srt(donnees, C.SORTIE / "video_finale.srt")
    soustitres.ecrire_ass(donnees, C.SORTIE / "video_finale.ass", titre=B.TITRE)
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

"""Export des sous-titres : paroles.json, .srt et .ass (karaoké mot par mot)."""
import json

from . import config as C
from .chanson import SECTIONS, TITRE


def _hms(t, sep=","):
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    ms = int(round((s - int(s)) * 1000))
    if ms == 1000:
        s, ms = s + 1, 0
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{ms:03d}"


def _ass_t(t):
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def ecrire_json(donnees, chemin, duree_audio, ratio):
    sections = [dict(nom=n, type=ty, debut=round(m0 * C.MESURE, 3), fin=round((m0 + nb) * C.MESURE, 3),
                     mesures=nb, decor=d) for n, ty, m0, nb, d, _ in SECTIONS]
    lignes = [dict(section=l["section"], texte=l["texte"], debut=round(l["debut"], 3), fin=round(l["fin"], 3),
                   mots=[dict(mot=m["texte"].replace(" ", " "), debut=round(m["debut"], 3),
                              fin=round(m["fin"], 3), couleur="#%02x%02x%02x" % m["couleur"]) for m in l["mots"]])
              for l in donnees["lignes"]]
    doc = dict(titre=TITRE, bpm=C.BPM, mesures=C.NB_MESURES, duree_audio=round(duree_audio, 3),
               ratio_recalage=round(ratio, 6), sections=sections, lignes=lignes)
    chemin.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def ecrire_srt(donnees, chemin):
    blocs = []
    for i, l in enumerate(donnees["lignes"], 1):
        blocs.append(f"{i}\n{_hms(l['aff_debut'])} --> {_hms(l['aff_fin'])}\n{l['texte']}\n")
    chemin.write_text("\n".join(blocs), encoding="utf-8")


def ecrire_ass(donnees, chemin):
    def bgr(c):
        return "&H00%02X%02X%02X&" % (c[2], c[1], c[0])
    entete = f"""[Script Info]
Title: {TITRE}
ScriptType: v4.00+
PlayResX: {C.LARGEUR}
PlayResY: {C.HAUTEUR}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Fredoka,86,&H003B3BFF,&H00FFFFFF,&H005C1C3A,&H80461428,-1,0,0,0,100,100,0,0,1,9,5,2,80,80,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for l in donnees["lignes"]:
        t = l["aff_debut"]
        morceaux = []
        for m in l["mots"]:
            avant = max(0.0, m["debut"] - t)
            if avant > 0.005:
                morceaux.append(f"{{\\k{round(avant * 100)}}}")
            duree = m["fin"] - m["debut"]
            morceaux.append(f"{{\\1c{bgr(m['couleur'])}\\kf{round(duree * 100)}}}{m['texte'].replace(chr(160), ' ')} ")
            t = m["fin"]
        ev.append(f"Dialogue: 0,{_ass_t(l['aff_debut'])},{_ass_t(l['aff_fin'])},Karaoke,,0,0,0,,{''.join(morceaux).rstrip()}")
    chemin.write_text(entete + "\n".join(ev) + "\n", encoding="utf-8")

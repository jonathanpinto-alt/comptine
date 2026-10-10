"""Voix chantée « style dessin animé » : Kokoro (TTS neuronal) qui CHANTE.

Le modèle Kokoro (StyleTTS2) prédit normalement lui-même la durée de chaque
phonème et la courbe de hauteur (F0). On modifie son graphe ONNX pour que ces
deux grandeurs deviennent des ENTRÉES : on lui impose les durées issues de la
grille rythmique et la mélodie. Le réseau produit alors directement une voix
chantée naturelle, parfaitement calée sur la musique.

Kokoro étant entraîné sur de la parole, il chante 9 demi-tons plus bas ; le
vocodeur WORLD remonte ensuite la voix à la bonne hauteur en décalant les
formants vers l'aigu (timbre enfantin, façon dessin animé). Dans les refrains,
deux voix d'enfants supplémentaires forment un petit chœur.
"""
import subprocess
from math import gcd

import numpy as np
import pyworld as pw
import soundfile as sf
from scipy import signal

from . import config as C
from .voix import SONORES, VOYELLES, reverb, segments_ligne

SR_K = 24000
TRAME = 600 / SR_K                    # 25 ms : unité de durée de Kokoro
VOIX_KOKORO = "ff_siwis"
MODELE = C.RACINE / "modeles" / "kokoro-v1.0.onnx"
VOIX_BIN = C.RACINE / "modeles" / "voices-v1.0.bin"
MODELE_CHANT = C.RACINE / "modeles" / "kokoro-v1.0-chant.onnx"
URL_MODELE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
TRANSPO_KOKORO = -9                   # demi-tons (zone confortable du modèle)
PRE = 0.30                            # silence avant chaque ligne (s)
POST = 0.25
VOYELLE_MAX = 6                       # trames (175 ms) chantées par Kokoro
CONSONNE_FACTEUR = 1.5
ACCENTS = True                        # accent tonique « ˈ » sur la dernière voyelle de chaque mot
PERIODE = 5.0                         # ms (trames WORLD)

# phonèmes MBROLA (SAMPA français d'espeak) -> IPA du vocabulaire Kokoro
SAMPA_IPA = {
    "a": "a", "A": "ɑ", "e": "e", "E": "ɛ", "i": "i", "o": "o", "O": "ɔ", "u": "u", "y": "y",
    "2": "ø", "9": "œ", "@": "ə", "a~": "ɑ̃", "e~": "ɛ̃", "o~": "ɔ̃", "9~": "œ̃",
    "S": "ʃ", "Z": "ʒ", "g": "ɡ", "R": "ʁ", "N": "ŋ", "J": "ɲ", "H": "ɥ",
}


def disponible():
    return MODELE.exists() and VOIX_BIN.exists()


def telecharger_modeles():
    """Télécharge le modèle Kokoro (≈ 350 Mo) depuis GitHub si absent."""
    MODELE.parent.mkdir(exist_ok=True)
    for f in (MODELE, VOIX_BIN):
        if not f.exists():
            print(f"   téléchargement de {f.name}…", flush=True)
            subprocess.run(["curl", "-sSL", "--fail", "-o", str(f), URL_MODELE + f.name], check=True)


def preparer_modele_chant():
    """Copie du modèle où durées et F0 deviennent des entrées."""
    if MODELE_CHANT.exists():
        return
    import onnx
    from onnx import TensorProto, helper
    m = onnx.load(str(MODELE))
    m.graph.input.append(helper.make_tensor_value_info("durees", TensorProto.FLOAT, [1, "n_jetons"]))
    m.graph.input.append(helper.make_tensor_value_info("f0", TensorProto.FLOAT, [1, 1, "n_f0"]))
    for n in m.graph.node:
        for k, i in enumerate(n.input):
            if i == "/encoder/Clip_output_0":            # durées prédites
                n.input[k] = "durees"
            elif i == "/encoder/F0_proj/Conv_output_0":  # courbe F0 prédite
                n.input[k] = "f0"
    onnx.save(m, str(MODELE_CHANT))


def resample(x, sr_in, sr_out):
    g = gcd(sr_in, sr_out)
    return signal.resample_poly(x, sr_out // g, sr_in // g)


def hauteur_cible(seg, temps):
    """Courbe F0 (Hz) de la mélodie aux instants `temps` (0 = non voisé)."""
    f0 = np.zeros(len(temps))
    for a, b, p, pts, _ in seg:
        m = (temps >= a) & (temps < b)
        if m.any() and p in SONORES:
            u = (temps[m] - a) / max(b - a, 1e-3) * 100
            f0[m] = np.interp(u, [q for q, _ in pts], [v for _, v in pts])
    return f0


def decaler_formants(sp, alpha):
    """Étire l'enveloppe spectrale vers les aigus (alpha > 1 : voix plus jeune)."""
    n = sp.shape[1]
    src = np.arange(n) / alpha
    out = np.empty_like(sp)
    for i in range(sp.shape[0]):
        out[i] = np.interp(src, np.arange(n), sp[i])
    return out


class Chanteuse:
    def __init__(self):
        import onnxruntime as ort
        from kokoro_onnx import Kokoro
        telecharger_modeles()
        preparer_modele_chant()
        self.k = Kokoro(str(MODELE), str(VOIX_BIN))
        self.voc = self.k.tokenizer.vocab
        self.sess = ort.InferenceSession(str(MODELE_CHANT))
        self.voix = self.k.voices[VOIX_KOKORO]
        self.cache = {}

    def jetons_et_durees(self, L, seg):
        """Jetons Kokoro + durées imposées (en trames de 25 ms).

        Les consonnes gardent leur durée cible ; les voyelles sont plafonnées
        (au-delà de ~2x leur durée naturelle, Kokoro articule mal) : la tenue
        des notes longues est faite ensuite par WORLD.
        Renvoie aussi, pour chaque phonème cible, sa plage (trame début, fin)."""
        tokens, durees, plages = [], [], []
        mots = []
        for syl in L.syllabes:
            for _ in syl.attaque + [syl.noyau] + syl.coda:
                mots.append(syl.mot)
        assert len(mots) == len(seg)
        derniere_voyelle = {}
        for k, (_, _, p, _, _) in enumerate(seg):
            if p in VOYELLES:
                derniere_voyelle[mots[k]] = k
        derniere_voyelle = set(derniere_voyelle.values())
        pre = int(round(PRE / TRAME))
        pos = pre
        prec = None
        for k, (a, b, p, _, _) in enumerate(seg):
            n = max(1, int(round((b - a) / TRAME)))
            if p in VOYELLES:
                n = min(n, VOYELLE_MAX)
            else:
                n = max(n, int(round(n * CONSONNE_FACTEUR)))
            if prec is not None and mots[k] != prec:      # espace entre les mots
                tokens.append(self.voc[" "])
                durees.append(0)
            prec = mots[k]
            ids = [self.voc[c] for c in SAMPA_IPA.get(p, p) if c in self.voc]
            if ACCENTS and k in derniere_voyelle:
                tokens.append(self.voc["ˈ"])
                durees.append(0)
            if len(ids) == 2:                             # voyelle nasale : voyelle + tilde
                durees += [n - n // 2, n // 2]
            else:
                durees += [n] + [0] * (len(ids) - 1)
            tokens += ids
            plages.append((pos, pos + n))
            pos += n
        fin = "!" if "!" in L.texte else ("." if "." in L.texte else ",")
        tokens.append(self.voc[fin])
        durees.append(1)
        return tokens, [pre] + durees + [int(round(POST / TRAME))], plages

    def chanter(self, L):
        """Kokoro chante la ligne (9 demi-tons plus bas).

        Renvoie (audio 24 kHz, segments cibles, plages des phonèmes en secondes)."""
        seg = segments_ligne(L)
        tokens, durees, plages = self.jetons_et_durees(L, seg)
        F = int(sum(durees))
        # F0 imposée : la note de chaque phonème sonore, à 2 valeurs par trame
        f0 = np.zeros(2 * F)
        for (a, b, p, pts, _), (i, j) in zip(seg, plages):
            if p in SONORES:
                f0[2 * i:2 * j] = np.interp(np.linspace(0, 100, 2 * (j - i)), [q for q, _ in pts],
                                            [v for _, v in pts])
        f0 = signal.savgol_filter(f0, 5, 2) * (f0 > 0)
        f0 *= 2 ** (TRANSPO_KOKORO / 12)
        style = self.voix[min(len(tokens), len(self.voix)) - 1].astype(np.float32)
        audio = self.sess.run(None, {
            "tokens": np.array([[0, *tokens, 0]], dtype=np.int64), "style": style,
            "speed": np.array([1.0], dtype=np.float32),
            "durees": np.array([durees], dtype=np.float32),
            "f0": f0.astype(np.float32)[None, None, :]})[0]
        x = np.asarray(audio, dtype=np.float64).ravel()
        return x, seg, [(i * TRAME, j * TRAME) for i, j in plages]

    def analyser(self, L):
        cle = (L.texte, L.mesure)
        if cle not in self.cache:
            x, seg, plages = self.chanter(L)
            f0, tps = pw.harvest(x, SR_K, f0_floor=80, f0_ceil=500, frame_period=PERIODE)
            sp = pw.cheaptrick(x, f0, tps, SR_K)
            ap = pw.d4c(x, f0, tps, SR_K)
            plages = recaler(plages, [p for _, _, p, _, _ in seg], f0 > 0)
            self.cache[cle] = (f0, sp, ap, seg, plages)
        return self.cache[cle]

    def voix_ligne(self, L, alpha=1.12, desaccord=0.0, retard=0.0):
        """Ligne chantée à la bonne hauteur, timbre enfantin -> (debut_s, audio 44,1 kHz)."""
        f0_src, sp, ap, seg, plages = self.analyser(L)
        # noeuds (temps cible -> temps source). Transitions jouées à vitesse naturelle,
        # coeur des voyelles tenu pour atteindre la durée de la note.
        kt, ks = [], []

        def noeud(t, s_):
            if kt and t <= kt[-1]:
                t = kt[-1] + 1e-4
            kt.append(t)
            ks.append(s_)

        for (a, b, p, _, _), (sa, sb) in zip(seg, plages):
            S, T = sb - sa, b - a
            noeud(a, sa)
            if p in VOYELLES and T > S * 1.2:
                noeud(a + 0.45 * S, sa + 0.45 * S)
                noeud(b - 0.35 * S, sb - 0.35 * S)
            noeud(b, sb)
        pas = PERIODE / 1000
        tau = np.arange(kt[0], kt[-1], pas)
        idx = np.clip(np.round(np.interp(tau, kt, ks) / pas).astype(int), 0, len(f0_src) - 1)

        f0 = hauteur_cible(seg, tau)
        # consonnes sonores non voisées dans la source : on garde le souffle
        sourde = f0_src[idx] == 0
        for a, b, p, _, _ in seg:
            if p not in VOYELLES:
                m = (tau >= a) & (tau < b)
                f0[m & sourde] = 0.0
        vois = f0 > 0
        if vois.sum() > 10:
            plein = np.interp(np.arange(len(f0)), np.flatnonzero(vois), f0[vois])
            f0 = np.where(vois, signal.savgol_filter(plein, 9, 2), 0.0)
        f0 *= 2 ** (desaccord / 1200)
        spn = decaler_formants(sp[idx], alpha) if alpha != 1.0 else sp[idx]
        y = pw.synthesize(np.ascontiguousarray(f0), np.ascontiguousarray(spn),
                          np.ascontiguousarray(ap[idx]), SR_K, PERIODE)
        n = int(0.012 * SR_K)
        if len(y) > 2 * n:
            y[:n] *= np.linspace(0, 1, n)
            y[-n:] *= np.linspace(1, 0, n)
        return kt[0] + retard, resample(y, SR_K, C.SR)


def recaler(plages, phonemes, voise):
    """Kokoro place l'audio légèrement en avance sur les durées imposées : on cherche
    le décalage (±150 ms) qui aligne le voisement attendu sur le voisement mesuré."""
    pas = PERIODE / 1000
    attendu = np.zeros(len(voise))
    for (a, b), p in zip(plages, phonemes):
        attendu[int(a / pas):int(b / pas)] = 1.0 if p in VOYELLES else (0.4 if p in SONORES else -1.0)
    v = np.where(voise, 1.0, -0.4)
    k = max(range(-30, 31), key=lambda k: float(np.dot(np.roll(attendu, k), v)))
    return [(max(0.0, a + k * pas), max(0.0, b + k * pas)) for a, b in plages]


def placer(buf, debut, y, gain=1.0):
    i = int(round(debut * C.SR))
    if i < 0:
        y, i = y[-i:], 0
    j = min(len(buf), i + len(y))
    if j > i:
        buf[i:j] += gain * y[: j - i]


def eclaircir(x):
    """EQ « voix de dessin animé » : coupe le grave, présence et brillance."""
    b, a = signal.butter(2, 140 / (C.SR / 2), "high")
    x = signal.lfilter(b, a, x)
    b, a = signal.butter(1, 3000 / (C.SR / 2), "high")
    return x + 0.4 * signal.lfilter(b, a, x)


def synthetiser(lignes, dossier):
    """Voix principale + chœur d'enfants (refrains) -> voix.wav stéréo 44,1 kHz."""
    ch = Chanteuse()
    n = int(round(C.DUREE_TOTALE * C.SR))
    lead = np.zeros(n)
    choeur_g = np.zeros(n)
    choeur_d = np.zeros(n)
    for i, L in enumerate(lignes):
        print(f"\r   ligne {i + 1}/{len(lignes)}", end="", flush=True)
        t, y = ch.voix_ligne(L)
        placer(lead, t, y)
        if L.type_section in ("refrain", "final", "intro", "outro"):
            t, y = ch.voix_ligne(L, alpha=1.22, desaccord=+8, retard=0.017)
            placer(choeur_g, t, y, 0.5)
            t, y = ch.voix_ligne(L, alpha=1.05, desaccord=-7, retard=0.029)
            placer(choeur_d, t, y, 0.5)
    print()
    lead = eclaircir(lead)
    choeur_g, choeur_d = eclaircir(choeur_g), eclaircir(choeur_d)
    gauche = lead + choeur_g + 0.3 * choeur_d
    droite = lead + choeur_d + 0.3 * choeur_g
    x = np.stack([gauche, droite], axis=1)
    x = np.tanh(1.5 * x / (np.max(np.abs(x)) + 1e-9)) / np.tanh(1.5)      # compression douce
    x = np.stack([reverb(x[:, 0], C.SR, mix=0.15, seed=1), reverb(x[:, 1], C.SR, mix=0.15, seed=2)], axis=1)
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
    sf.write(dossier / "voix.wav", x.astype(np.float32), C.SR)
    sf.write(dossier / "voix_lead.wav", (lead / (np.max(np.abs(lead)) + 1e-9) * 0.9).astype(np.float32), C.SR)
    return x.astype(np.float32)

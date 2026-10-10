"""Mixage voix + musique avec pydub, export audio_final.wav."""
import numpy as np
import soundfile as sf
from pydub import AudioSegment

from . import config as C


def vers_segment(x):
    """numpy float (n,) ou (n,2) -> AudioSegment 16 bits stéréo."""
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    return AudioSegment(pcm.tobytes(), frame_rate=C.SR, sample_width=2, channels=2)


def rms_actif(x):
    """RMS (dBFS) sur les passages non silencieux."""
    m = x if x.ndim == 1 else x.mean(axis=1)
    bloc = int(0.05 * C.SR)
    n = len(m) // bloc
    r = np.sqrt(np.mean(m[: n * bloc].reshape(n, bloc) ** 2, axis=1))
    r = r[r > r.max() * 0.05]
    return 20 * np.log10(np.sqrt(np.mean(r ** 2)) + 1e-12)


def mixer(voix, musique, chemin, ecart_db=8.0):
    """Voix au premier plan, musique à -8 dB sous la voix."""
    gain_musique = (rms_actif(voix) - ecart_db) - rms_actif(musique)
    seg_voix = vers_segment(voix * 0.5)          # marge pour la sommation
    seg_mus = vers_segment(musique * 0.5).apply_gain(gain_musique)
    mix = seg_mus.overlay(seg_voix)
    mix = mix.normalize(headroom=1.0)            # crête à -1 dBFS
    mix.export(chemin, format="wav")
    x, sr = sf.read(chemin)
    duree = len(x) / sr
    return duree, gain_musique

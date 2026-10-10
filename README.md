# 🐮 « Bonjour la ferme ! » — comptine vidéo 100 % générée par code

Une comptine originale en français pour les 2-5 ans, dans un style à la Cocomelon : couleurs vives, personnages ronds qui rebondissent en rythme, karaoké coloré mot par mot.
Tout est produit par `python main.py` : paroles, mélodie, accompagnement, voix chantée, sous-titres, animation et montage final.

| | |
|---|---|
| Durée | **2 min 30,5 s** (69 mesures à 110 BPM, 4/4, do majeur → ré majeur au dernier refrain) |
| Vidéo | 1920×1080, 30 i/s, H.264 + AAC |
| Structure | intro → couplet 1 → refrain → couplet 2 → refrain → pont calme → couplet 3 → refrain final ×2 → outro |

## Fichiers produits (`sortie/`)

| Fichier | Contenu |
|---|---|
| `video_finale.mp4` | la vidéo finale |
| `audio_final.wav` | le mixage (voix devant, musique ≈ 8 dB dessous) |
| `paroles.json` | les sections et les lignes, avec le texte, les mots, les débuts/fins en secondes et la couleur de chaque mot |
| `video_finale.srt` | sous-titres classiques, une ligne par phrase |
| `video_finale.ass` | sous-titres karaoké (`\kf` mot par mot, couleurs de la palette) |
| `musique.mid` | l'accompagnement en MIDI |

## Installation

Testé sous Ubuntu 24.04 avec Python 3.13.

```bash
# outils système : ffmpeg, synthèse MIDI, voix chantée
sudo apt install ffmpeg fluidsynth fluid-soundfont-gm espeak-ng mbrola mbrola-fr4 libcairo2-dev

# bibliothèques Python
pip install -r requirements.txt
```

macOS (Homebrew) : `brew install ffmpeg fluid-synth espeak-ng cairo`. La voix MBROLA `fr4` se télécharge à part, et il faut une soundfont General MIDI. Les chemins sont réglables dans `comptine/config.py` et `comptine/voix.py`.

## Lancement

```bash
python main.py                    # tout générer (environ 3-4 min sur 4 cœurs)
python main.py --rapide           # vidéo d'essai en 960×540 → sortie/video_essai.mp4
python main.py --audio-seulement  # audio et sous-titres uniquement
python main.py --apercu 30        # une image PNG à t = 30 s
```

Le script vérifie que la durée audio est comprise entre 2 min 25 et 2 min 35. Il vérifie aussi la durée de la vidéo finale.

## Fonctionnement

```
main.py
comptine/
  chanson.py      paroles, structure (mesures), accords, gabarits mélodiques
  voix.py         phonétisation (espeak-ng), syllabes, rythme, voix chantée (MBROLA)
  musique.py      arrangement MIDI (pretty_midi) → FluidSynth
  mixage.py       mixage pydub, musique à -8 dB sous la voix, export WAV
  soustitres.py   paroles.json, .srt, .ass
  personnages.py  7 animaux en SVG (normal / clignement / chante) → sprites (cairosvg)
  decors.py       8 décors animés en cairo
  rendu.py        animation, karaoké, transitions, rendu parallèle + ffmpeg
assets/
  fonts/Fredoka.ttf (licence OFL)
  personnages/*.svg (générés)
```

**Voix chantée.** Chaque mot est phonétisé par espeak-ng et découpé en syllabes. Chaque syllabe reçoit une durée sur une grille de doubles croches, et une note tirée d'un gabarit mélodique. On écrit ensuite un fichier `.pho` MBROLA qui précise, pour chaque phonème, sa durée exacte et sa hauteur : la voix suit réellement la mélodie, avec un léger vibrato sur les notes longues. Les consonnes sont placées avant le temps pour que la voyelle tombe sur la note. Comme les durées sont imposées, le calage du karaoké est exact. Les timings sont ensuite recalés sur la durée réelle du WAV, avec un ratio d'environ 1,000.

> Pourquoi pas edge-tts ? edge-tts produit une voix *parlée*, et il a besoin d'un accès WebSocket aux serveurs de Microsoft, qui n'était pas disponible dans l'environnement de génération. MBROLA fonctionne hors ligne et permet de *chanter* (hauteur et durée imposées).

**Arrangement par section.**
- Intro : le xylophone annonce le refrain.
- Couplets : ukulélé, basse et maracas, avec de petites réponses de xylophone.
- Refrains : piano, claps, tambourin et glockenspiel qui double la voix.
- Pont : cordes et boîte à musique, sans batterie.
- Refrain final : cuivres, charleston, xylophone et modulation d'un ton au 2ᵉ passage.
- Outro : le glockenspiel, puis l'accord final et une cymbale.

**Décors.**
- Intro : lever de soleil sur la ferme.
- Couplet 1 : le pré, avec le coq et la vache.
- Refrain : la grange et tous les animaux.
- Couplet 2 : la mare, avec le canard et le cochon.
- Pont : ciel étoilé, lune qui chante et mouton qui dort.
- Couplet 3 : la forêt, avec le cheval qui galope suivi des poussins.
- Refrain final : la fête avec arc-en-ciel, fanions, ballons et confettis.
- Outro : coucher de soleil.

On passe d'un décor à l'autre par une transition « bulle ». Les animaux rebondissent sur le temps, avec écrasement à l'atterrissage. Ils ouvrent la bouche quand ils chantent et clignent des yeux. Ils sautent quand on chante leur cri (« meuh », « coin-coin », « groin-groin », « bê-bê », « hop »…).

**Karaoké.** Chaque mot passe du blanc à une couleur de la palette tournante (rouge, orange, jaune, vert, bleu, violet, rose) quand il est chanté, avec un petit rebond. Le texte est en police Fredoka Bold, avec un contour épais et une ombre.

## Paroles

**Couplet 1**
Le soleil se lève, cocorico !
Le coq chante tout là-haut.
La vache dit « meuh » dans le pré,
Elle a du bon lait à donner !

**Refrain**
Bonjour la ferme, bonjour, bonjour !
Les animaux chantent tout autour !
Meuh, coin-coin, groin-groin, bê-bê,
On tape des mains, on tape des pieds !

**Couplet 2**
Le petit canard fait coin-coin,
Il nage, il nage dans le bassin.
Le cochon rose fait groin-groin,
Il se roule dans la boue, c'est bien !

**Pont**
La lune brille, il fait tout noir,
Les animaux disent bonsoir.
Le mouton fait un doux bê-bê,
Chut… tout le monde va rêver.

**Couplet 3**
Cocorico, le jour est là !
Le cheval galope, hop là, hop là !
Les poussins font piou-piou-piou,
Tout le monde se lève, debout, debout !

**Refrain final ×2** (« Encore une fois ! »), puis « Au revoir les amis ! »

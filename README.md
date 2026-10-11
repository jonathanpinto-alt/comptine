# Comptines vidéo 100 % générées par code

Deux comptines originales en français pour les 2-5 ans, style dessin animé 3D pour enfants :
- **« C'est l'heure du bain ! »** (3 min) → `python main.py --chanson bain` → `sortie/bain/` — [voir plus bas](#-cest-lheure-du-bain---3-min)
- **« Bonjour la ferme ! »** (2 min 30) → `python main.py` → `sortie/`

# 🐮 « Bonjour la ferme ! »

Une comptine originale en français pour les 2-5 ans, dans un style de dessin animé 3D pour enfants : couleurs vives, animaux ronds aux gros yeux brillants qui rebondissent en rythme, voix chantée enfantine avec petit chœur, karaoké coloré mot par mot.
Tout est produit par `python main.py` : paroles, mélodie, accompagnement, voix chantée, modèles 3D, sous-titres, animation et montage final.

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
# outils système : ffmpeg, synthèse MIDI, phonétisation, 3D
sudo apt install ffmpeg fluidsynth fluid-soundfont-gm espeak-ng mbrola mbrola-fr4 libcairo2-dev blender

# bibliothèques Python
pip install -r requirements.txt
```

Au premier lancement, le modèle de voix Kokoro (environ 350 Mo, licence Apache 2.0) est téléchargé depuis GitHub dans `modeles/`. Blender tourne en arrière-plan, sans écran : le moteur Eevee fonctionne en rendu logiciel. Les rendus 3D (personnages, décors, accessoires) sont mis en cache dans `assets/rendus3d/`.

macOS (Homebrew) : `brew install ffmpeg fluid-synth espeak-ng cairo`. La voix MBROLA `fr4` se télécharge à part, et il faut une soundfont General MIDI. Les chemins sont réglables dans `comptine/config.py` et `comptine/voix.py`.

## Lancement

```bash
python main.py                    # tout générer (environ 5 min sur 4 cœurs, rendus 3D en cache)
python main.py --rapide           # vidéo d'essai en 960×540 → sortie/video_essai.mp4
python main.py --audio-seulement  # audio et sous-titres uniquement
python main.py --apercu 30        # une image PNG à t = 30 s
python main.py --refaire-3d       # refaire les modèles 3D dans Blender (environ 10 min)
python main.py --voix mbrola      # ancienne voix de synthèse, sans modèle neuronal
```

Le script vérifie que la durée audio est comprise entre 2 min 25 et 2 min 35. Il vérifie aussi la durée de la vidéo finale.

## Fonctionnement

```
main.py
comptine/
  chanson.py      paroles, structure (mesures), accords, gabarits mélodiques
  voix.py         phonétisation (espeak-ng), syllabes, rythme ; voix MBROLA de secours
  voix_kokoro.py  voix neuronale Kokoro qui chante, WORLD, timbre enfantin, chœur
  musique.py      arrangement MIDI (pretty_midi) → FluidSynth
  mixage.py       mixage pydub, musique à -8 dB sous la voix, export WAV
  soustitres.py   paroles.json, .srt, .ass
  blender3d.py    modélisation 3D par code (bpy) et rendu Eevee
  rendu3d.py      lance Blender et met les rendus en cache
  fonds3d.py      composition : ciel animé, astres et nuages 3D, décor, effets
  decors.py       primitives 2D (dégradés, confettis, fanions, lucioles…)
  rendu.py        animation, karaoké, transitions, rendu parallèle + ffmpeg
assets/
  fonts/Fredoka.ttf (licence OFL)
  rendus3d/       sprites 3D pré-rendus (générés par Blender)
```

### Voix « dessin animé »

Le modèle de synthèse vocale neuronal [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) (voix française `ff_siwis`) prédit normalement lui-même la durée de chaque phonème et la courbe de hauteur. `voix_kokoro.py` modifie son graphe ONNX pour que ces deux grandeurs deviennent des **entrées**. On lui impose ainsi le rythme de la chanson et la mélodie, et il **chante**.

Les étapes sont les suivantes :
1. Chaque mot est phonétisé (espeak-ng), découpé en syllabes, et chaque syllabe reçoit une note et une durée sur la grille rythmique (110 BPM).
2. Kokoro chante la ligne 9 demi-tons plus bas, dans sa zone de confort. Les voyelles sont plafonnées à environ 150 ms, au-delà de quoi il articule mal.
3. Le vocodeur WORLD tient le cœur des voyelles jusqu'à la durée de la note, remonte la voix à la bonne hauteur (avec portamento et vibrato) et décale les formants vers l'aigu pour un **timbre enfantin**.
4. Dans les refrains, l'intro et l'outro, deux voix d'enfants supplémentaires, légèrement désaccordées, décalées et réparties à gauche et à droite, forment un **petit chœur**.

La voix tombe exactement sur la mélodie (écart inférieur à 0,1 demi-ton) et sur le rythme, ce qui rend le karaoké précis.

> Pourquoi pas edge-tts ? edge-tts produit une voix *parlée*, et il a besoin d'un accès WebSocket aux serveurs de Microsoft, qui n'était pas disponible dans l'environnement de génération. Kokoro fonctionne hors ligne et peut être piloté finement.

### Musique

**Arrangement par section.**
- Intro : le xylophone annonce le refrain.
- Couplets : ukulélé, basse et maracas, avec de petites réponses de xylophone.
- Refrains : piano, claps, tambourin et glockenspiel qui double la voix.
- Pont : cordes et boîte à musique, sans batterie.
- Refrain final : cuivres, charleston, xylophone et modulation d'un ton au 2ᵉ passage.
- Outro : le glockenspiel, puis l'accord final et une cymbale.

### Animation 3D

`blender3d.py` construit tout par code avec Blender : ellipsoïdes, cylindres biseautés, prismes et courbes, matériaux doux légèrement translucides (subsurface), yeux brillants avec reflets.
- **Éclairage** : style studio, avec lumière principale douce, contre-jour et ambiance de ciel.
- **Rendu** : moteur Eevee, avec ombres douces, occlusion ambiante et bloom.
- **7 animaux**, chacun en 3 états (normal, yeux fermés, bouche ouverte).
- **8 décors**, un par section :
  - intro : lever de soleil ;
  - couplet 1 : le pré ;
  - refrains : la grange ;
  - couplet 2 : la mare ;
  - pont : la nuit étoilée ;
  - couplet 3 : la forêt ;
  - refrain final : la fête avec arc-en-ciel ;
  - outro : le coucher de soleil.
- **Accessoires** : soleil et lune avec un visage, étoiles, nuages, ballons.

`rendu.py` et `fonds3d.py` assemblent ces rendus image par image :
- **Fond** : ciel en dégradé pastel animé, soleil et lune qui se lèvent ou se couchent, nuages qui défilent, étoiles qui scintillent.
- **Caméra** : léger travelling avant pour la profondeur.
- **Personnages** : ils rebondissent sur le temps (avec écrasement à l'atterrissage), ouvrent la bouche quand ils chantent, clignent des yeux et sautent quand on chante leur cri (« meuh », « coin-coin »…).
- **Transitions** : en forme de bulle entre les sections.

### Karaoké

Chaque mot passe du blanc à une couleur de la palette tournante (rouge, orange, jaune, vert, bleu, violet, rose) au moment où il est chanté, avec un petit rebond. Le texte est en police Fredoka Bold, avec un contour épais et une ombre.

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

---

# 🛁 « C'est l'heure du bain ! » — 3 min

Comptine sur la routine du bain. **Objectif éducatif** : les gestes d'hygiène (se laver les mains, les pieds, les cheveux, se rincer, se brosser les dents), compter jusqu'à trois et se calmer avant le dodo.

```bash
python main.py --chanson bain                    # tout (rendus 3D en cache) → sortie/bain/video_finale.mp4
python main.py --chanson bain --audio-seulement  # audio + sous-titres
python main.py --chanson bain --apercu 107       # une image PNG à t = 107 s
python main.py --chanson bain --rapide           # essai 960×540
python main.py --chanson bain --refaire-3d       # refaire les rendus Blender (environ 40 min)
```

| | |
|---|---|
| Durée | **3 min 00 s** pile (72 mesures à 96 BPM, 4/4, do majeur) |
| Vidéo | 1920×1080, 30 i/s, H.264 + AAC, karaoké mot par mot incrusté |
| Fichiers | `sortie/bain/` : `video_finale.mp4`, `audio_final.wav`, `paroles.json` (mots, temps, couleurs, plans), `.srt`, `.ass`, `musique.mid` |

## Structure et montage

Deux scènes par section, dans l'ordre demandé **1, 2, 3, 4, 5, 3, 4, 3, 4, 5, 6, 6, 3, 4, 5, 7** :

| Section | Mesures | Temps | Scènes |
|---|---|---|---|
| Intro (2 mesures instrumentales + 2 lignes) | 0–6 | 0:00–0:15 | 1 → 2 |
| Couplet 1 | 6–14 | 0:15–0:35 | 3 → 4 |
| Refrain (+ 2 mesures « splash » au xylophone) | 14–24 | 0:35–1:00 | 5 → 3 |
| Couplet 2 | 24–32 | 1:00–1:20 | 4 → 3 |
| Refrain | 32–42 | 1:20–1:45 | 4 → 5 |
| Couplet 3 | 42–50 | 1:45–2:05 | 6 → 6 |
| Refrain | 50–60 | 2:05–2:30 | 3 → 4 |
| Fin (berceuse) + outro | 60–72 | 2:30–3:00 | 5 → 7 |

La 2ᵉ scène de chaque section commence sur la 3ᵉ ligne chantée.

**Scènes** (personnage original : petit garçon de 2 ans, boucles blondes, grands yeux, pyjama bleu à étoile jaune) :
1. debout dans la salle de bain colorée, timide, il regarde la baignoire pleine de mousse et le canard jaune ;
2. dans le bain, il rit et éclabousse, bulles colorées ;
3. gros plan : il se frotte les mains (bulles), puis les montre propres, fier (étincelles) ;
4. il se lave les cheveux, couronne de mousse, il rit dans un petit miroir flottant (avec son reflet) ;
5. dans sa serviette blanche à capuche de canard, il saute de joie ;
6. il compte les bulles en pointant du doigt : chaque bulle s'allume avec son chiffre sur « un, deux, trois » ;
7. en pyjama, il se brosse les dents devant un miroir rigolo (reflet) ; texte « Propre et prêt pour dodo ! ».

Un canard en caoutchouc original (avec son petit chapeau de marin) flotte dans le bain.

## Son
- **Mélodie** écrite note par note (`comptine/bain/chanson.py`), simple et répétitive, refrain accrocheur « Splash splash splash ».
- **Voix** : la voix Kokoro qui chante (voir plus haut), avec des formants peu décalés pour une voix plus chaleureuse ; **chœur de trois voix d'enfants** sur les refrains.
- **Musique** : ukulélé et marimba (couplets), piano, claps, tambourin et glockenspiel (refrains), berceuse à la boîte à musique et au célesta pour la fin.
- **Bruitages** synthétisés : bulles qui éclatent, éclaboussures sur chaque « splash », couinement du canard.

## 3D
`comptine/bain/blender_bain.py` modélise tout par code dans Blender (Eevee) : le garçon et ses bras posés par cinématique inverse, 4 cadrages (salle de bain large, baignoire, gros plan, lavabo), le canard et le miroir à main.
Pour chaque cadrage, Blender rend :
- le décor seul ;
- le garçon dans chaque pose et expression, avec le décor en *holdout* : le bord de la baignoire, l'eau et la mousse le découpent exactement.

`comptine/bain/rendu.py` anime ensuite le tout image par image : poses calées sur le tempo, clignements, sauts, bulles, gouttes, reflets dans les miroirs, travellings et transitions en bulle.

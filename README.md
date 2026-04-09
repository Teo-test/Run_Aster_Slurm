# Run Aster Slurm — Outils de calcul et d'analyse

Ensemble d'outils pour soumettre des calculs **Code_Aster** via **Slurm** et exploiter les résultats.

---

## Démarrage rapide

| Outil | Commande de lancement |
|---|---|
| Soumettre un calcul | `bash run_aster.sh` |
| Soumettre un calcul (CLI) | `bash run_aster.sh [OPTIONS] DOSSIER/` |
| Analyser un `.resu` | `bash Outil_annexes/parse_resu.sh` |
| Analyser un `.resu` (CLI) | `bash Outil_annexes/parse_resu.sh [OPTIONS] FICHIER.resu` |
| Comparer des CSV | `python Outil_annexes/comparecsv_v3.py [fichiers.csv ...]` |
| Extraire des graphes PPTX | `python Outil_annexes/pptx_chart_extractor_v2.py [fichier.pptx]` |

> **Navigation commune aux outils Python** :
> - `↑↓` pour naviguer
> - `Espace` pour cocher/décocher
> - `Entrée` pour valider
> - `Ctrl+C` pour annuler.

---

## `run_aster.sh` — Soumission de calculs Code_Aster

### Prérequis

- Slurm (`sbatch`, `squeue`, `scancel`)
- Code_Aster installé sous `ASTER_ROOT` ou accessible via un module Lmod
- Scratch partagé entre nœud login et nœuds de calcul

### Configuration (en tête du script)

```bash
ASTER_ROOT="${ASTER_ROOT:-/opt/code_aster}"  # chemin vers Code_Aster
ASTER_MODULE="${ASTER_MODULE:-}"             # module Lmod (laisser vide si non utilisé)
SCRATCH_BASE="${SCRATCH_BASE:-/scratch}"     # scratch partagé login ↔ calcul
```

Ces variables peuvent être surchargées depuis le shell avant d'appeler le script :
```bash
export ASTER_ROOT=/logiciels/code_aster/17.1
bash run_aster.sh mon_etude/
```

### Mode interactif (sans argument)

```bash
bash run_aster.sh
```

Lance un wizard en 4 étapes avec navigation par flèches :
1. **Dossier d'étude** — détection automatique des dossiers contenant un `.comm`
2. **Preset** — `court` / `moyen` / `long` / Manuel (saisie champ par champ)
3. **Options** — cases à cocher : `--follow`, `--keep-scratch`, `--dry-run`
4. **Récapitulatif + confirmation** avant soumission

### Mode CLI (avec arguments)

```bash
bash run_aster.sh [OPTIONS] [DOSSIER_ETUDE]
```

#### Fichiers d'entrée

| Option | Description |
|---|---|
| `-C, --comm FILE` | Fichier `.comm` (auto-détecté si absent) |
| `-M, --med  FILE` | Maillage MED (auto-détecté si absent) |
| `-A, --mail FILE` | Maillage ASTER natif (auto-détecté si absent) |
| `-B, --base DIR`  | Dossier de base pour **POURSUITE** (contient `glob.*` / `pick.*`) |

Les fichiers `.py`, `.dat`, `.para`, `.include`, `.mfront` présents dans le dossier sont copiés automatiquement dans le scratch. Les fichiers `glob.*` / `pick.*` / `vola.*` du dossier `-B` (ou auto-détectés dans le dossier d'étude) sont également copiés.

#### Ressources Slurm

| Option | Défaut | Description |
|---|---|---|
| `-P, --preset NOM`    | —          | `court`, `moyen` ou `long` |
| `-p, --partition NOM` | `court`    | Partition Slurm |
| `-n, --nodes N`       | `1`        | Nombre de nœuds |
| `-t, --ntasks N`      | `1`        | Tâches MPI |
| `-c, --cpus N`        | `1`        | CPUs par tâche |
| `-m, --mem MEM`       | `5G`       | Mémoire (ex: `8G`, `512M`) |
| `-T, --time DUREE`    | `05:00:00` | Durée max (`J-HH:MM:SS`, `HH:MM:SS`) |

| Preset  | Partition | Mémoire | Durée max |
|---------|-----------|---------|-----------|
| `court` | court     | 2 G     | 5 h       |
| `moyen` | normal    | 20 G    | 3 jours   |
| `long`  | long      | 50 G    | 30 jours  |

Les options passées **après** `-P` surchargent le preset : `-P moyen -t 8`

#### Sorties supplémentaires `-R`

```bash
-R "type:unite,type:unite,..."   # ex: -R "rmed:81,csv:38"
```

| Unité | Type   | Extension | Description |
|:-----:|--------|-----------|-------------|
| 6     | `mess` | `.mess`   | Log d'exécution |
| 8     | `resu` | `.resu`   | Résultats texte |
| 38    | `csv`  | `.csv`    | Tableau (IMPR_TABLE) |
| 80    | `rmed` | `.rmed`    | Résultats MED (ParaVis) |
| 81+   | `rmed` | `.med`    | Résultats MED supplémentaires |

Dans le `.comm` : `IMPR_RESU(UNITE=81, ...)` / `IMPR_TABLE(UNITE=38, ...)`

#### Autres options

| Option | Description |
|---|---|
| `-f, --follow`    | Suit le job : spinner PENDING → `tail -f` automatique en RUNNING → bilan final. `Ctrl+C` détache sans annuler. |
| `-q, --quiet`     | Sortie minimale — affiche uniquement le job ID (utile pour scripts) |
| `--keep-scratch`  | Conserve le scratch après le calcul (utile pour debug) |
| `--dry-run`       | Affiche la commande `sbatch` sans la lancer |
| `--no-validate`   | Désactive la validation du `.comm` avant soumission |
| `--debug`         | Active `set -x` sur le nœud de calcul |
| `-h, --help`      | Affiche l'aide |

### Exemples

```bash
# Mode interactif
bash run_aster.sh

# Dossier explicite avec preset
bash run_aster.sh -P moyen mon_etude/

# Preset surchargé
bash run_aster.sh -P moyen -t 8 -m 16G mon_etude/

# Résultats supplémentaires
bash run_aster.sh -P moyen -R "rmed:81,csv:38" mon_etude/

# Calcul en poursuite (POURSUITE) avec base explicite
bash run_aster.sh -P moyen -B mon_etude_thermo/run_12345 mon_etude_meca/

# Suivre le job en temps réel
bash run_aster.sh -P court -f mon_etude/

# Récupérer uniquement le job ID (pour scripts)
JOB=$(bash run_aster.sh -q mon_etude/)

# Vérifier sans lancer
bash run_aster.sh --dry-run -P moyen mon_etude/
```

### Fonctionnement interne

```
Nœud login                              Nœud de calcul
──────────────────────────────────────  ──────────────────────────────────────
bash run_aster.sh mon_etude/            sbatch relance CE MÊME script
  ├─ Détecte .comm / .med / .mail         avec __RUN_PHASE=EXEC
  ├─ Crée scratch/<etude>_ts_pid/
  ├─ Copie fichiers d'entrée            ├─ Charge Code_Aster (module ou chemin)
  ├─ Génère le .export                  ├─ Lance run_aster (MPI interne)
  └─ sbatch ──────────────────────►     ├─ Analyse .mess (<A> <F> <S>)
                                        ├─ Rapatrie → run_JOBID/
                                        ├─ Lien symbolique latest/
                                        └─ Bilan final
```

Un `trap SIGTERM/EXIT` garantit que les résultats sont **toujours rapatriés**, même en cas de `scancel` ou de timeout.

### Structure des fichiers

```
$SCRATCH_BASE/$USER/<etude>_<ts>_<pid>/   ← scratch (calcul)
  ├─ mon_etude.comm / .med / .export
  ├─ mon_etude.mess / .resu / _resu.med
  └─ REPE_OUT/

$STUDY_DIR/                              ← dossier d'étude
  ├─ aster_<jobid>.out / .err            ← logs Slurm
  ├─ latest -> run_<jobid>/              ← lien vers le dernier run
  └─ run_<jobid>/                        ← résultats rapatriés
      └─ mon_etude.mess / .resu / .med
```

### Suivi d'un calcul

```bash
squeue -j <JOB_ID>
tail -f mon_etude/aster_<JOB_ID>.out
ls mon_etude/latest/
scancel <JOB_ID>    # annule — rapatriement automatique déclenché
```

---

## `parse_resu.sh` — Analyse des fichiers `.resu` Code_Aster

Navigation par flèches identique à `run_aster.sh`. Aucune dépendance externe (bash + awk).

### Lancement

```bash
# Mode interactif (détection auto des .resu dans le dossier courant)
bash Outil_annexes/parse_resu.sh

# Sur un fichier ou un dossier précis
bash Outil_annexes/parse_resu.sh mon_etude/run_12345/calcul.resu
bash Outil_annexes/parse_resu.sh mon_etude/run_12345/
```

### Mode interactif — étapes

1. **Sélection du fichier** `.resu` (menu flèches si plusieurs trouvés, profondeur 3)
2. **Scan automatique** → tableau récapitulatif des blocs : champ, numéro d'ordre, instant, localisation
3. **Sélection des blocs** à traiter (cases à cocher)
4. **Action** → Export CSV / Statistiques / Affichage terminal / Les deux
5. **Dossier de sortie** (si export CSV)

### Mode CLI

| Option | Description |
|---|---|
| `-f, --field NOM`  | Filtrer sur un champ (`DEPL`, `SIEF_ELNO`, `EQUI_ELNO`…) |
| `-o, --ordre N`    | Filtrer sur un numéro d'ordre (0 = tous) |
| `-a, --all`        | Exporter tous les blocs en CSV |
| `--stats`          | Afficher statistiques min/max/moy (sans CSV) |
| `--csv`            | Forcer l'export CSV (un fichier par bloc) |
| `-O, --outdir DIR` | Dossier de sortie (défaut : même dossier que le `.resu`) |
| `-q, --quiet`      | Sortie minimale |

### Exemples CLI

```bash
# Export CSV du champ DEPL (tous les instants)
bash Outil_annexes/parse_resu.sh -f DEPL --csv calcul.resu

# Statistiques sur les contraintes
bash Outil_annexes/parse_resu.sh --stats -f SIEF_ELNO calcul.resu

# Tout exporter vers un dossier dédié
bash Outil_annexes/parse_resu.sh --all -O ./resultats/ mon_etude/run_12345/

# Un ordre précis
bash Outil_annexes/parse_resu.sh -f DEPL -o 3 --csv calcul.resu
```

### Format des fichiers produits

Un CSV par bloc sélectionné, nommé `CHAMP_ordN_instX.csv` :

```
NOEUD,DX,DY,DZ
N1,0.000000E+00,0.000000E+00,0.000000E+00
N2,5.461820E-05,9.945110E-07,-6.324510E-07
```

| Localisation | Colonnes identifiant |
|---|---|
| `NOEU` (nœuds) | `NOEUD` |
| `ELNO` (nœuds par élément) | `MAILLE, NOEUD` |
| `ELGA` (points de Gauss) | `MAILLE, POINT` |

### Limites connues (v1.0)

- Blocs avec **wrapping de colonnes** (>6 composantes) : seul le premier groupe de colonnes est extrait
- Format **`IMPR_TABLE`** (colonnes libres) : non pris en charge
- Blocs **`ELGA SOUS_POINT`** : support partiel

---

## `comparecsv_v3.py` — Comparateur interactif de CSV

Navigation par flèches dans tous les menus. Requiert `questionary`.

### Installation

```bash
pip install pandas matplotlib numpy questionary
pip install openpyxl   # optionnel — export Excel
```

### Lancement

```bash
# Mode interactif (menu principal)
python Outil_annexes/comparecsv_v3.py

# Avec fichiers pré-chargés
python Outil_annexes/comparecsv_v3.py fichier1.csv fichier2.csv

# Avec séparateur forcé
python Outil_annexes/comparecsv_v3.py data.csv --sep ";"
```

### Fonctionnalités

**Graphes** — pour chaque type, le titre et les labels des axes sont personnalisables :

| Type | Description |
|---|---|
| Ligne | X vs Y, multi-séries, multi-fichiers |
| Scatter | Nuage de points numériques |
| Barres | Groupées par catégorie |
| Histogramme | Distribution d'une colonne (bins configurables) |
| Boîte à moustaches | Comparaison de distributions |
| Aire empilée | Cumul de plusieurs colonnes |
| Heatmap | Matrice de corrélation |

**Données :**

| Fonctionnalité | Description |
|---|---|
| Auto-détection séparateur | `,` `;` `\t` `\|` espace |
| Aperçu + statistiques | Résumé colonnes, `describe()` |
| Mini-barre ASCII | Aperçu aligné de chaque colonne dans les menus |
| Diviser par groupes | Sépare un CSV dont les lignes ont des colonnes différentes remplies (ex : deux séries de mesures entrelacées) |

**Export / Fusion :**

| Format | Options |
|---|---|
| CSV | Choix du séparateur (`,` `;` `\t` `\|`) |
| TSV | Tabulation forcée |
| TXT | Séparé par espaces |
| JSON | Format `records`, `table` ou `index` |
| Excel `.xlsx` | Nom de feuille personnalisable |
| Parquet | Si `pyarrow` disponible |

Lors de l'export, toutes les colonnes sont présélectionnées — décocher celles à exclure avec `Espace`.

### Cas d'usage : CSV avec groupes de colonnes différents

Pour un fichier où certaines lignes ont `Temperature`/`Wind_Speed` remplis et d'autres ont `Clothing`/`Food` remplis :

1. Charger le fichier
2. Menu → **Diviser par groupes de colonnes**
3. Le script détecte et sépare automatiquement les deux groupes en datasets distincts

---

## `pptx_chart_extractor_v2.py` — Extracteur de graphes PowerPoint

Navigation par flèches dans tous les menus. Utilise uniquement la bibliothèque standard Python pour lire le PPTX (`zipfile` + `xml.etree.ElementTree`).

### Installation

```bash
pip install pandas matplotlib numpy questionary
```

### Lancement

```bash
# Mode interactif (menu principal)
python Outil_annexes/pptx_chart_extractor_v2.py

# Avec fichier pré-chargé
python Outil_annexes/pptx_chart_extractor_v2.py presentation.pptx

# Avec dossier de sortie personnalisé
python Outil_annexes/pptx_chart_extractor_v2.py presentation.pptx -o resultats/
```

### Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| Détection des graphes | Parcourt toutes les slides, liste chaque graphe avec slide, type et titre |
| Résumé | Tableau récapitulatif (N°, slide, type, lignes, colonnes, titre) |
| Détail | Affiche les séries, colonnes et un aperçu des 10 premières lignes |
| Affichage | Rendu matplotlib à l'écran et/ou sauvegarde PNG (150 dpi) |
| Export CSV | Un fichier par graphe : `graphe_01_titre.csv` |
| Export complet | Tous les graphes → CSV + PNG en une commande |

**Types de graphes supportés :** `lineChart`, `barChart`, `scatterChart`, `pieChart`, `doughnutChart`, `areaChart`, `radarChart`, `stockChart`, `surfaceChart` (et variantes 3D)

**Sélection des graphes :** choix rapide "Tous" ou sélection individuelle par cases à cocher.

---

## `run_aster_light.sh` — Version minimale de debug

Script simplifié pour diagnostiquer des problèmes de configuration. Affiche l'environnement complet (PATH, modules, exécutable trouvé, contenu du `.export`) avant de lancer le calcul.

### Lancement

```bash
# Calcul simple
bash Outil_annexes/run_aster_light.sh mon_etude/

# Calcul en poursuite (STAT_NON_LINE avec base existante)
bash Outil_annexes/run_aster_light.sh -B mon_etude_thermo/run_12345 mon_etude_meca/
bash Outil_annexes/run_aster_light.sh -B mon_etude_thermo/latest    mon_etude_meca/
```

| Option | Description |
|---|---|
| `-B, --base CHEMIN` | Dossier de base pour **POURSUITE** (doit contenir `glob.*` et `pick.*`) |
| `-h, --help` | Affiche l'aide |

---

## Auteur

Téo LEROY

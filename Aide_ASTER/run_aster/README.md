# run_aster — Soumission Code_Aster via Slurm

## Structure

```
run_aster/
├── run_aster.sh          ← point d'entrée (orchestrateur ~150 lignes)
├── conf/
│   └── config.sh         ← ✏️  SEUL fichier à éditer pour votre calculateur
└── lib/
    ├── ui.sh             ← couleurs, menus interactifs, barre de progression
    ├── utils.sh          ← _find_first, _count_files
    ├── comm.sh           ← analyse et validation du .comm
    ├── export.sh         ← validation TYPE/UNITE, génération du .export
    ├── slurm.sh          ← soumission sbatch et suivi de job
    └── exec.sh           ← phase 2 : exécution sur le nœud de calcul
```

## Utilisation

```bash
bash run_aster.sh           # wizard interactif
bash run_aster.sh --help    # aide
```

## Adapter au calculateur

Éditer **uniquement** `conf/config.sh` :

```bash
ASTER_ROOT="/chemin/vers/code_aster"
ASTER_MODULE="code_aster/17.1"
SCRATCH_BASE="/scratch"

# Presets Slurm (court / moyen / long)
PRESET_MEM=([court]="4G" [moyen]="32G" [long]="100G")
PRESET_TIME=([court]="02:00:00" [moyen]="2-00:00:00" [long]="14-00:00:00")
```

## Ajouter une étude paramétrique

Pour soumettre plusieurs variantes (taux de dépôt, énergie...) :

```bash
#!/usr/bin/env bash
# submit_param.sh — boucle de soumission pour l'étude macro-dépôt

FLUX_VALUES=(5e6 8e6 12e6)
TAUX_VALUES=(0.5 1.0 2.0)

for flux in "${FLUX_VALUES[@]}"; do
  for taux in "${TAUX_VALUES[@]}"; do
    CASE="MD_F${flux}_T${taux}"
    # Préparer le dossier du cas à partir d'un template
    cp -r cases/template "cases/${CASE}"
    # Substituer les paramètres dans le .comm
    sed -i "s/__FLUX__/${flux}/g; s/__TAUX__/${taux}/g" "cases/${CASE}/macro_depot.comm"
    # Soumettre directement sans wizard (non interactif)
    STUDY_DIR="$(realpath cases/${CASE})" bash run_aster.sh
  done
done
```

## Extension de lib/exec.sh

Pour ajouter un post-traitement automatique après le calcul,
ajouter dans `lib/exec.sh` après `collect_results` :

```bash
# Post-traitement Python (optionnel)
if [ -f "${__STUDY_DIR}/post/extract.py" ]; then
    log "Post-traitement..."
    python3 "${__STUDY_DIR}/post/extract.py" "${dest}" >> "${dest}/post.log" 2>&1
fi
```

#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  conf/config.sh — Configuration globale run_aster
#
#  Seul fichier à éditer pour adapter le script à votre calculateur.
#  Sourcé par run_aster.sh et par lib/*.sh
# ══════════════════════════════════════════════════════════════════

# ── Chemins calculateur ───────────────────────────────────────────
ASTER_ROOT="${ASTER_ROOT:-/opt/code_aster}"
ASTER_MODULE="${ASTER_MODULE:-}"
SCRATCH_BASE="${SCRATCH_BASE:-/scratch}"

# ── Ressources Slurm — valeurs par défaut ────────────────────────
DEFAULT_PARTITION="court"
DEFAULT_NODES=1
DEFAULT_NTASKS=1
DEFAULT_CPUS=1
DEFAULT_MEM="5G"
DEFAULT_TIME="05:00:00"

# ── Presets (court / moyen / long) ───────────────────────────────
declare -A PRESET_PARTITION=([court]="court"  [moyen]="normal" [long]="long")
declare -A PRESET_NODES=(    [court]=1        [moyen]=1        [long]=1)
declare -A PRESET_NTASKS=(   [court]=1        [moyen]=1        [long]=1)
declare -A PRESET_MEM=(      [court]="2G"     [moyen]="20G"    [long]="50G")
declare -A PRESET_TIME=(     [court]="05:00:00" [moyen]="03-00:00:00" [long]="30-00:00:00")

# ── Extensions rapatriées depuis le scratch ───────────────────────
# Ajouter ici toute extension spécifique à vos calculs
COLLECT_EXTENSIONS=(mess resu med csv table dat pos rmed txt vtu vtk py base)

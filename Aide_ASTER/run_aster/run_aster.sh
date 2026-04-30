#!/usr/bin/env bash
#===============================================================================
#  run_aster.sh — Point d'entrée principal
#===============================================================================
#
#  Usage :  bash run_aster.sh [-h|--help]
#
#  ARCHITECTURE
#  ─────────────────────────────────────────────────────────────────
#    run_aster.sh          ← ce fichier (orchestrateur, ~100 lignes)
#    conf/config.sh        ← SEUL fichier à éditer (chemins, presets, ressources)
#    lib/ui.sh             ← couleurs, menus interactifs, barre de progression
#    lib/comm.sh           ← analyse et validation du .comm
#    lib/export.sh         ← validation TYPE/UNITE et génération du .export
#    lib/slurm.sh          ← soumission sbatch et suivi de job
#    lib/exec.sh           ← phase 2 : exécution sur le nœud de calcul
#
#  PHASES
#  ─────────────────────────────────────────────────────────────────
#    Phase 1 — nœud login  : wizard interactif, validation, soumission
#    Phase 2 — nœud calcul : lancé automatiquement par sbatch
#
#  NOTE MPI : run_aster gère MPI en interne — ne PAS encapsuler dans srun.
#
#  Auteur  : Teo LEROY
#  Version : 15.0
#===============================================================================

# ── Localisation du script (pour les sources et le self-submit) ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Chargement de la configuration et des bibliothèques ──────────
# shellcheck source=conf/config.sh
source "${SCRIPT_DIR}/conf/config.sh"
# shellcheck source=lib/ui.sh
source "${SCRIPT_DIR}/lib/ui.sh"
# shellcheck source=lib/utils.sh
source "${SCRIPT_DIR}/lib/utils.sh"

# ════════════════════════════════════════════════════════════════
#  PHASE 2 — NŒUD DE CALCUL
#  Déclenché par sbatch via __RUN_PHASE=EXEC
# ════════════════════════════════════════════════════════════════
if [ "${__RUN_PHASE:-}" = "EXEC" ]; then
    source "${SCRIPT_DIR}/lib/exec.sh"
    exit $?
fi

# ════════════════════════════════════════════════════════════════
#  PHASE 1 — NŒUD LOGIN (MODE INTERACTIF)
# ════════════════════════════════════════════════════════════════

source "${SCRIPT_DIR}/lib/comm.sh"
source "${SCRIPT_DIR}/lib/export.sh"
source "${SCRIPT_DIR}/lib/slurm.sh"

# ── Aide ─────────────────────────────────────────────────────────
usage() {
    cat <<'EOF'
USAGE
  bash run_aster.sh [-h|--help]

  Lance le wizard interactif pour configurer et soumettre un calcul
  Code_Aster via Slurm.

  Navigation : flèches ↑↓, espace pour cocher, entrée pour valider.

FICHIERS DE CONFIGURATION
  conf/config.sh   Chemins calculateur, presets Slurm, extensions à rapatrier

VARIABLES D'ENVIRONNEMENT (surchargent conf/config.sh)
  ASTER_ROOT     Chemin de Code_Aster  (défaut : /opt/code_aster)
  ASTER_MODULE   Module à charger sur le nœud de calcul
  SCRATCH_BASE   Racine du scratch     (défaut : /scratch)
EOF
    exit 0
}

case "${1:-}" in -h|--help) usage ;; esac

# ── Variables d'état du wizard ────────────────────────────────────
STUDY_DIR=""; COMM=""; MED=""; MAIL=""; BASE_DIR=""
PARTITION=""; NODES=""; NTASKS=""; CPUS=""; MEM=""; TIME_LIMIT=""
RESULTS=""; KEEP_SCRATCH=0; DRY_RUN=0; DEBUG=0; FOLLOW=0; NO_VALIDATE=0

banner

# ── Vérification initiale des chemins ────────────────────────────
if [ ! -d "$ASTER_ROOT" ]; then
    warn "ASTER_ROOT = $ASTER_ROOT  (dossier absent)" >/dev/tty
    saisir "Chemin ASTER_ROOT" "$ASTER_ROOT"; ASTER_ROOT="$_SAISIE"
fi
if [ ! -d "$SCRATCH_BASE" ]; then
    warn "SCRATCH_BASE = $SCRATCH_BASE  (dossier absent)" >/dev/tty
    saisir "Chemin SCRATCH_BASE" "$SCRATCH_BASE"; SCRATCH_BASE="$_SAISIE"
fi

# ════════════════════════════════════════════════════════════════
#  WIZARD — 6 étapes avec navigation Ctrl+C pour revenir en arrière
# ════════════════════════════════════════════════════════════════
_STEP=0
while true; do
case $_STEP in

# ── Étape 1 : Dossier d'étude ─────────────────────────────────
0)  _ETAPE_COURANTE=0; afficher_progression; section "Dossier d'étude"
    local_dossiers=()
    while IFS= read -r d; do local_dossiers+=("$d"); done < <(
        find . -maxdepth 2 -name "*.comm" -printf '%h\n' 2>/dev/null | sort -u | sed 's|^\./\?||;/^$/d'
    )
    [ ${#local_dossiers[@]} -eq 0 ] && local_dossiers=(".")
    if [ ${#local_dossiers[@]} -gt 1 ]; then
        menu_fleches "Dossier contenant le .comm :" "${local_dossiers[@]}"
        [ "$_MENU_IDX" -eq -1 ] && { warn "Annulé." >/dev/tty; exit 0; }
        STUDY_DIR="${local_dossiers[$_MENU_IDX]}"
    else
        saisir "Dossier d'étude" "${local_dossiers[0]}"; STUDY_DIR="$_SAISIE"
    fi
    STUDY_DIR="$(realpath "$STUDY_DIR")"
    STUDY_NAME="$(basename "$STUDY_DIR")"
    [ ! -d "$STUDY_DIR" ] && { err "Dossier introuvable : $STUDY_DIR"; continue; }
    [[ "$STUDY_NAME" =~ [,=\ ] ]] && { err "Nom de dossier invalide (pas de virgule/espace/=) : '$STUDY_NAME'"; continue; }
    ok "Dossier : ${STUDY_DIR}" >/dev/tty; _STEP=1 ;;

# ── Étape 2 : Détection des fichiers ─────────────────────────
1)  _ETAPE_COURANTE=1; afficher_progression; section "Détection des fichiers"
    COMM=$(_find_first "$STUDY_DIR" "*.comm")
    [ -z "$COMM" ] && { err "Aucun .comm dans $STUDY_DIR"; _STEP=0; continue; }
    COMM="$(realpath "$COMM")"; ok ".comm : $(basename "$COMM")" >/dev/tty
    MED=$(_find_first "$STUDY_DIR" "*.med" 2>/dev/null || true)
    [ -n "$MED" ] && { MED="$(realpath "$MED")"; ok ".med  : $(basename "$MED")" >/dev/tty; }
    MAIL=$(_find_first "$STUDY_DIR" "*.mail" 2>/dev/null || true)
    [ -n "$MAIL" ] && { MAIL="$(realpath "$MAIL")"; ok ".mail : $(basename "$MAIL")" >/dev/tty; }
    BASE_DIR=""
    if grep -q "POURSUITE" "$COMM" 2>/dev/null; then
        echo "" >/dev/tty; info "POURSUITE détecté dans le .comm" >/dev/tty
        saisir "Dossier de base (glob.*/pick.*) — vide = auto-détection" ""
        [ -n "$_SAISIE" ] && BASE_DIR="$_SAISIE"
    fi
    shopt -s nullglob
    local_aux=("$STUDY_DIR"/*.py "$STUDY_DIR"/*.dat "$STUDY_DIR"/*.para \
               "$STUDY_DIR"/*.include "$STUDY_DIR"/*.mfront)
    shopt -u nullglob
    [ ${#local_aux[@]} -gt 0 ] && info "${#local_aux[@]} fichier(s) auxiliaire(s) détecté(s)" >/dev/tty
    _STEP=2 ;;

# ── Étape 3 : Sorties du calcul ───────────────────────────────
2)  _ETAPE_COURANTE=2; afficher_progression; section "Sorties du calcul"
    RESULTS=""
    info "Analyse de $(basename "$COMM")..." >/dev/tty
    _parse_comm_outputs "$COMM"
    if [ ${#_COMM_OUTPUTS[@]} -gt 0 ]; then
        local_labels=()
        for _item in "${_COMM_OUTPUTS[@]}"; do local_labels+=("${_item%%|*}"); done
        menu_cases "Sorties supplémentaires à inclure :" "${local_labels[@]}"
        [ "$_MENU_IDX" -eq -1 ] && { _STEP=$((_STEP - 1)); continue; }
        local_sel_results=""
        for _idx in "${_MENU_ITEMS[@]}"; do
            _item="${_COMM_OUTPUTS[$_idx]}"
            local_type="${_item#*|}"; local_type="${local_type%%|*}"
            local_unite="${_item##*|}"
            [ -n "$local_sel_results" ] && local_sel_results+=","
            local_sel_results+="${local_type}:${local_unite}"
        done
        [ -n "$local_sel_results" ] && RESULTS="$local_sel_results"
    else
        info "Aucune sortie supplémentaire détectée — défaut : .mess, .resu, .rmed (u80)" >/dev/tty
    fi
    _STEP=3 ;;

# ── Étape 4 : Ressources Slurm ────────────────────────────────
3)  _ETAPE_COURANTE=3; afficher_progression; section "Ressources Slurm"
    menu_fleches "Preset de ressources :" \
        "court   — ${PRESET_PARTITION[court]}   │ ${PRESET_MEM[court]}   │ ${PRESET_TIME[court]}" \
        "moyen   — ${PRESET_PARTITION[moyen]}  │ ${PRESET_MEM[moyen]}  │ ${PRESET_TIME[moyen]}" \
        "long    — ${PRESET_PARTITION[long]}    │ ${PRESET_MEM[long]}  │ ${PRESET_TIME[long]}" \
        "Manuel  — saisir les valeurs"
    [ "$_MENU_IDX" -eq -1 ] && { _STEP=$((_STEP - 1)); continue; }
    local_presets=(court moyen long)
    if [ "$_MENU_IDX" -lt 3 ]; then
        local_p="${local_presets[$_MENU_IDX]}"
        PARTITION="${PRESET_PARTITION[$local_p]}"; NODES="${PRESET_NODES[$local_p]}"
        NTASKS="${PRESET_NTASKS[$local_p]}";       MEM="${PRESET_MEM[$local_p]}"
        TIME_LIMIT="${PRESET_TIME[$local_p]}";     CPUS="$DEFAULT_CPUS"
    else
        saisir "Partition"        "$DEFAULT_PARTITION"; PARTITION="$_SAISIE"
        saisir "Nb nœuds"         "$DEFAULT_NODES";     NODES="$_SAISIE"
        saisir "Nb tâches MPI"    "$DEFAULT_NTASKS";    NTASKS="$_SAISIE"
        saisir "CPUs par tâche"   "$DEFAULT_CPUS";      CPUS="$_SAISIE"
        saisir "Mémoire (ex: 8G)" "$DEFAULT_MEM";       MEM="$_SAISIE"
        saisir "Durée max"        "$DEFAULT_TIME";       TIME_LIMIT="$_SAISIE"
    fi
    : "${PARTITION:=$DEFAULT_PARTITION}" "${NODES:=$DEFAULT_NODES}" "${NTASKS:=$DEFAULT_NTASKS}"
    : "${CPUS:=$DEFAULT_CPUS}"           "${MEM:=$DEFAULT_MEM}"     "${TIME_LIMIT:=$DEFAULT_TIME}"
    _STEP=4 ;;

# ── Étape 5 : Options ─────────────────────────────────────────
4)  _ETAPE_COURANTE=4; afficher_progression; section "Options"
    FOLLOW=0; KEEP_SCRATCH=0; DRY_RUN=0; NO_VALIDATE=0
    menu_cases "Options :" \
        "Suivre le job en temps réel" \
        "Conserver le scratch après le calcul" \
        "Dry-run — afficher sans soumettre" \
        "Désactiver la validation du .comm"
    [ "$_MENU_IDX" -eq -1 ] && { _STEP=$((_STEP - 1)); continue; }
    for idx in "${_MENU_ITEMS[@]}"; do
        case "$idx" in 0) FOLLOW=1 ;; 1) KEEP_SCRATCH=1 ;; 2) DRY_RUN=1 ;; 3) NO_VALIDATE=1 ;; esac
    done
    _STEP=5 ;;

# ── Étape 6 : Récapitulatif et confirmation ───────────────────
5)  _ETAPE_COURANTE=5; afficher_progression; section "Récapitulatif"
    echo "" >/dev/tty
    printf "    ${BOLD}%-14s${NC} %s\n" "Dossier"    "$STUDY_DIR"             >/dev/tty
    printf "    ${BOLD}%-14s${NC} %s\n" ".comm"       "$(basename "$COMM")"   >/dev/tty
    [ -n "$MED"  ] && printf "    ${BOLD}%-14s${NC} %s\n" ".med"  "$(basename "$MED")"  >/dev/tty
    [ -n "$MAIL" ] && printf "    ${BOLD}%-14s${NC} %s\n" ".mail" "$(basename "$MAIL")" >/dev/tty
    echo -e "    ${DIM}──────────────────────────────────────${NC}" >/dev/tty
    printf "    ${BOLD}%-14s${NC} %s\n" "Partition"   "$PARTITION"  >/dev/tty
    printf "    ${BOLD}%-14s${NC} %s\n" "Nœuds"       "$NODES"      >/dev/tty
    printf "    ${BOLD}%-14s${NC} %s\n" "Tâches MPI"  "$NTASKS"     >/dev/tty
    printf "    ${BOLD}%-14s${NC} %s\n" "CPUs/tâche"  "$CPUS"       >/dev/tty
    printf "    ${BOLD}%-14s${NC} %s\n" "Mémoire"     "$MEM"        >/dev/tty
    printf "    ${BOLD}%-14s${NC} %s\n" "Durée max"   "$TIME_LIMIT" >/dev/tty
    if [ -n "$RESULTS" ]; then
        echo -e "    ${DIM}──────────────────────────────────────${NC}" >/dev/tty
        printf "    ${BOLD}%-14s${NC} %s\n" "Sorties" "$RESULTS" >/dev/tty
    fi
    local_opts_str=""
    [ "$FOLLOW"       = "1" ] && local_opts_str+="follow "
    [ "$KEEP_SCRATCH" = "1" ] && local_opts_str+="keep-scratch "
    [ "$DRY_RUN"      = "1" ] && local_opts_str+="dry-run "
    [ "$NO_VALIDATE"  = "1" ] && local_opts_str+="no-validate "
    if [ -n "$local_opts_str" ]; then
        echo -e "    ${DIM}──────────────────────────────────────${NC}" >/dev/tty
        printf "    ${BOLD}%-14s${NC} %s\n" "Options" "$local_opts_str" >/dev/tty
    fi
    echo "" >/dev/tty
    menu_fleches "Confirmer la soumission ?" "✅  Soumettre le calcul" "❌  Annuler"
    [ "$_MENU_IDX" -eq -1 ] && { _STEP=$((_STEP - 1)); continue; }
    [ "$_MENU_IDX" -ne 0  ] && { warn "Annulé."; exit 0; }
    break ;;

esac
done

# ════════════════════════════════════════════════════════════════
#  EXÉCUTION — set -euo pipefail à partir d'ici
# ════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Validation du .comm ──────────────────────────────────────────
if [ "$NO_VALIDATE" -eq 0 ]; then
    if ! valider_comm "$COMM" "$STUDY_DIR" "$MED" "$MAIL" "$RESULTS"; then
        err "Validation du .comm échouée — corrigez les erreurs ci-dessus"
        exit 1
    fi
fi

# ── Préparation du scratch ───────────────────────────────────────
section "Préparation du scratch"
SCRATCH="${SCRATCH_BASE}/${USER}/${STUDY_NAME}_$(date +%s)_$$"
mkdir -p "$SCRATCH"
ok "Scratch : $SCRATCH" >/dev/tty

cp "$COMM" "$SCRATCH/"
[ -n "$MED"  ] && cp "$MED"  "$SCRATCH/"
[ -n "$MAIL" ] && cp "$MAIL" "$SCRATCH/"

shopt -s nullglob
for f in "$STUDY_DIR"/*.py "$STUDY_DIR"/*.dat "$STUDY_DIR"/*.para \
         "$STUDY_DIR"/*.include "$STUDY_DIR"/*.mfront; do
    cp "$f" "$SCRATCH/"
done
shopt -u nullglob

# Base (POURSUITE)
_BASE_SRC="${BASE_DIR:-}"
if [ -z "$_BASE_SRC" ]; then
    shopt -s nullglob
    _base_check=("$STUDY_DIR"/glob.* "$STUDY_DIR"/pick.* "$STUDY_DIR"/vola.*)
    shopt -u nullglob
    [ ${#_base_check[@]} -gt 0 ] && _BASE_SRC="$STUDY_DIR"
fi
if [ -n "$_BASE_SRC" ]; then
    [ -d "$_BASE_SRC" ] || { err "Dossier base introuvable : $_BASE_SRC"; exit 1; }
    shopt -s nullglob
    for f in "$_BASE_SRC"/glob.* "$_BASE_SRC"/pick.* "$_BASE_SRC"/vola.*; do cp -a "$f" "$SCRATCH/"; done
    shopt -u nullglob
    ok "Base : $_BASE_SRC → scratch" >/dev/tty
fi

# ── Génération du .export ────────────────────────────────────────
section "Génération du .export"
EXPORT="${SCRATCH}/${STUDY_NAME}.export"
if ! generer_export "$EXPORT" "$SCRATCH" "$STUDY_NAME" \
                    "$COMM" "$MED" "$MAIL" "$RESULTS" \
                    "$TIME_LIMIT" "$MEM" "$NTASKS"; then
    rm -rf "$SCRATCH"
    exit 1
fi
ok "Export : $EXPORT" >/dev/tty
while IFS= read -r line; do info "  $line" >/dev/tty; done < "$EXPORT"

# ── Soumission ───────────────────────────────────────────────────
section "Soumission Slurm"
SELF="$(realpath "$0")"
_JOB_ID=""
if ! soumettre_job "$SELF" "$STUDY_DIR" "$STUDY_NAME" "$SCRATCH" "$EXPORT" \
                   "$ASTER_ROOT" "$ASTER_MODULE" "$PARTITION" "$NODES" \
                   "$NTASKS" "$CPUS" "$MEM" "$TIME_LIMIT" \
                   "$KEEP_SCRATCH" "$DEBUG" "$DRY_RUN"; then
    exit 1
fi

# ── Suivi optionnel ──────────────────────────────────────────────
[ "$FOLLOW" = "1" ] && [ -n "$_JOB_ID" ] && \
    suivre_job "$_JOB_ID" "${STUDY_DIR}/aster_run_${_JOB_ID}.out" "$STUDY_DIR"

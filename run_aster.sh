#!/bin/bash
#===============================================================================
#  run_aster.sh — Lanceur Code_Aster via SLURM (sbatch)
#
#  Usage :
#    sbatch [options sbatch] run_aster.sh [options]
#
#  Exemples :
#    sbatch run_aster.sh                          # défauts : partition=court, 4 cpus, 8G
#    sbatch run_aster.sh -p moyen -t 12:00:00 -c 8 -m 32G
#    sbatch run_aster.sh -p long  -c 16 -m 64G --mail user@mail.com
#    sbatch run_aster.sh --comm mon_etude.comm --mesh maillage.med
#
#  Le script :
#    1. Détecte automatiquement les fichiers .comm, .export et maillage
#    2. Crée un dossier temporaire sur $SCRATCH
#    3. Copie les fichiers nécessaires
#    4. Lance Code_Aster
#    5. Rapatrie les résultats dans le dossier d'origine
#    6. Nettoie le dossier temporaire
#    7. Écrit un log consultable en direct (tail -f)
#===============================================================================

#=== Valeurs par défaut ========================================================
PARTITION="court"
TIME=""
NCPUS=4
MEMORY="8G"
MAIL=""
JOBNAME=""
ASTER_VERSION=""
COMM_FILE=""
EXPORT_FILE=""
MESH_FILE=""
EXTRA_FILES=""
KEEP_SCRATCH=0

#=== Aide ======================================================================
usage() {
    cat <<EOF
┌──────────────────────────────────────────────────────────────────────┐
│  run_aster.sh — Lanceur Code_Aster via SLURM                       │
└──────────────────────────────────────────────────────────────────────┘

Usage : sbatch run_aster.sh [OPTIONS]

OPTIONS :
  -p, --partition PART   Partition SLURM : court | moyen | long   [court]
  -t, --time HH:MM:SS   Temps max (défaut selon partition)
  -c, --cpus N           Nombre de CPUs                           [4]
  -m, --memory MEM       Mémoire (ex: 8G, 16G, 64G)              [8G]
  -j, --jobname NOM      Nom du job SLURM                         [aster_<étude>]
  -v, --version VER      Version Code_Aster (ex: stable, 16.4)   [stable]
      --comm FICHIER     Fichier .comm (auto-détecté sinon)
      --export FICHIER   Fichier .export (auto-détecté sinon)
      --mesh FICHIER     Fichier maillage (auto-détecté sinon)
      --extra F1,F2,...  Fichiers supplémentaires à copier
      --mail EMAIL       Adresse e-mail pour notifications SLURM
      --keep-scratch     Ne pas supprimer le dossier scratch après calcul
  -h, --help             Afficher cette aide

PARTITIONS (temps par défaut) :
  court   →  2:00:00
  moyen   → 12:00:00
  long    → 72:00:00

SUIVI EN DIRECT :
  Après le lancement, un fichier .log est créé dans le dossier courant.
  Pour suivre l'avancée :
    tail -f aster_<jobid>.log

EOF
    exit 0
}

#=== Parsing des arguments =====================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--partition)  PARTITION="$2";    shift 2 ;;
        -t|--time)       TIME="$2";         shift 2 ;;
        -c|--cpus)       NCPUS="$2";        shift 2 ;;
        -m|--memory)     MEMORY="$2";       shift 2 ;;
        -j|--jobname)    JOBNAME="$2";      shift 2 ;;
        -v|--version)    ASTER_VERSION="$2"; shift 2 ;;
        --comm)          COMM_FILE="$2";    shift 2 ;;
        --export)        EXPORT_FILE="$2";  shift 2 ;;
        --mesh)          MESH_FILE="$2";    shift 2 ;;
        --extra)         EXTRA_FILES="$2";  shift 2 ;;
        --mail)          MAIL="$2";         shift 2 ;;
        --keep-scratch)  KEEP_SCRATCH=1;    shift   ;;
        -h|--help)       usage ;;
        *)
            echo "Option inconnue : $1"
            usage
            ;;
    esac
done

#=== Temps par défaut selon la partition =======================================
if [[ -z "$TIME" ]]; then
    case "$PARTITION" in
        court)  TIME="02:00:00" ;;
        moyen)  TIME="12:00:00" ;;
        long)   TIME="72:00:00" ;;
        *)      TIME="02:00:00" ;;
    esac
fi

#=== Dossier de travail (work) = là où on lance sbatch =========================
WORKDIR="$(pwd)"

#=== Auto-détection des fichiers ===============================================
log_info()  { echo "[INFO]  $(date '+%H:%M:%S') — $*"; }
log_warn()  { echo "[WARN]  $(date '+%H:%M:%S') — $*"; }
log_error() { echo "[ERROR] $(date '+%H:%M:%S') — $*"; }
die()       { log_error "$*"; exit 1; }

# --- Fichier .comm ---
if [[ -z "$COMM_FILE" ]]; then
    COMM_FILES=( "$WORKDIR"/*.comm )
    if [[ ${#COMM_FILES[@]} -eq 0 || ! -f "${COMM_FILES[0]}" ]]; then
        die "Aucun fichier .comm trouvé dans $WORKDIR"
    elif [[ ${#COMM_FILES[@]} -gt 1 ]]; then
        die "Plusieurs fichiers .comm trouvés. Précisez avec --comm : ${COMM_FILES[*]}"
    fi
    COMM_FILE="${COMM_FILES[0]}"
fi
[[ -f "$COMM_FILE" ]] || die "Fichier .comm introuvable : $COMM_FILE"
COMM_FILE="$(realpath "$COMM_FILE")"
STUDY_NAME="$(basename "$COMM_FILE" .comm)"

# --- Fichier .export ---
if [[ -z "$EXPORT_FILE" ]]; then
    EXPORT_FILES=( "$WORKDIR"/*.export )
    if [[ ${#EXPORT_FILES[@]} -eq 1 && -f "${EXPORT_FILES[0]}" ]]; then
        EXPORT_FILE="${EXPORT_FILES[0]}"
    fi
fi
if [[ -n "$EXPORT_FILE" && -f "$EXPORT_FILE" ]]; then
    EXPORT_FILE="$(realpath "$EXPORT_FILE")"
    HAS_EXPORT=1
else
    HAS_EXPORT=0
fi

# --- Fichier maillage (.med, .mail, .mgib, .mmed, .unv) ---
if [[ -z "$MESH_FILE" ]]; then
    MESH_PATTERNS=("$WORKDIR"/*.med "$WORKDIR"/*.mail "$WORKDIR"/*.mgib "$WORKDIR"/*.mmed "$WORKDIR"/*.unv)
    FOUND_MESHES=()
    for f in "${MESH_PATTERNS[@]}"; do
        [[ -f "$f" ]] && FOUND_MESHES+=("$f")
    done
    if [[ ${#FOUND_MESHES[@]} -eq 0 ]]; then
        die "Aucun fichier maillage (.med/.mail/.mgib/.mmed/.unv) trouvé"
    elif [[ ${#FOUND_MESHES[@]} -gt 1 ]]; then
        log_warn "Plusieurs maillages trouvés, utilisation du premier : ${FOUND_MESHES[0]}"
    fi
    MESH_FILE="${FOUND_MESHES[0]}"
fi
[[ -f "$MESH_FILE" ]] || die "Fichier maillage introuvable : $MESH_FILE"
MESH_FILE="$(realpath "$MESH_FILE")"

#=== Nom du job ================================================================
if [[ -z "$JOBNAME" ]]; then
    JOBNAME="aster_${STUDY_NAME}"
fi

#=== Fichier log (dans work, consultable en direct) ============================
LOGFILE="${WORKDIR}/${JOBNAME}.log"

#===============================================================================
#  On ré-appelle ce même script via sbatch avec les directives SLURM
#  si on n'est PAS déjà dans un contexte SLURM (SLURM_JOB_ID absent).
#===============================================================================
if [[ -z "${SLURM_JOB_ID:-}" ]]; then

    # Construction des directives sbatch
    SBATCH_ARGS=(
        --partition="$PARTITION"
        --time="$TIME"
        --cpus-per-task="$NCPUS"
        --mem="$MEMORY"
        --job-name="$JOBNAME"
        --output="$LOGFILE"
        --error="$LOGFILE"
    )

    if [[ -n "$MAIL" ]]; then
        SBATCH_ARGS+=(--mail-type=BEGIN,END,FAIL --mail-user="$MAIL")
    fi

    # On relance ce script dans SLURM en passant les mêmes arguments
    SELF_ARGS=()
    SELF_ARGS+=(-p "$PARTITION" -t "$TIME" -c "$NCPUS" -m "$MEMORY")
    SELF_ARGS+=(--comm "$COMM_FILE" --mesh "$MESH_FILE")
    [[ $HAS_EXPORT -eq 1 ]]  && SELF_ARGS+=(--export "$EXPORT_FILE")
    [[ -n "$ASTER_VERSION" ]] && SELF_ARGS+=(-v "$ASTER_VERSION")
    [[ -n "$EXTRA_FILES" ]]   && SELF_ARGS+=(--extra "$EXTRA_FILES")
    [[ -n "$MAIL" ]]          && SELF_ARGS+=(--mail "$MAIL")
    [[ $KEEP_SCRATCH -eq 1 ]] && SELF_ARGS+=(--keep-scratch)
    SELF_ARGS+=(-j "$JOBNAME")

    JOBID=$(sbatch "${SBATCH_ARGS[@]}" "$0" "${SELF_ARGS[@]}" 2>&1)

    if [[ $? -eq 0 ]]; then
        JOBID_NUM=$(echo "$JOBID" | grep -oP '\d+')
        cat <<EOF

╔══════════════════════════════════════════════════════════════════════╗
║  Job soumis avec succès !                                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  Job ID     : ${JOBID_NUM}
║  Partition   : ${PARTITION}
║  Temps max   : ${TIME}
║  CPUs        : ${NCPUS}
║  Mémoire     : ${MEMORY}
║  Étude       : ${STUDY_NAME}
║  Comm        : $(basename "$COMM_FILE")
║  Maillage    : $(basename "$MESH_FILE")
║  Log         : ${LOGFILE}
╠══════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  SUIVI EN DIRECT :                                                 ║
║    tail -f ${LOGFILE}
║                                                                    ║
║  AUTRES COMMANDES :                                                ║
║    squeue -j ${JOBID_NUM}            # état du job                 ║
║    scancel ${JOBID_NUM}              # annuler le job              ║
║                                                                    ║
╚══════════════════════════════════════════════════════════════════════╝
EOF
    else
        echo "ERREUR lors de la soumission : $JOBID"
        exit 1
    fi
    exit 0
fi

#===============================================================================
#  À PARTIR D'ICI, ON EST DANS LE JOB SLURM (exécuté par le noeud de calcul)
#===============================================================================

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║  Code_Aster — Début du calcul                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
log_info "Job ID        : $SLURM_JOB_ID"
log_info "Noeud         : $SLURM_NODELIST"
log_info "Partition     : $SLURM_JOB_PARTITION"
log_info "CPUs          : $SLURM_CPUS_PER_TASK"
log_info "Mémoire       : $MEMORY"
log_info "Dossier work  : $WORKDIR"
log_info "Étude         : $STUDY_NAME"
log_info "Fichier .comm : $COMM_FILE"
log_info "Maillage      : $MESH_FILE"
echo ""

#=== Détection du dossier SCRATCH ==============================================
if [[ -z "${SCRATCH:-}" ]]; then
    # Essayer des chemins courants si $SCRATCH n'est pas défini
    for candidate in "/scratch/$USER" "/scratch/$(whoami)" "/tmp"; do
        if [[ -d "$candidate" ]]; then
            SCRATCH="$candidate"
            break
        fi
    done
fi
[[ -d "$SCRATCH" ]] || die "Dossier SCRATCH introuvable ($SCRATCH). Définissez \$SCRATCH."
log_info "SCRATCH       : $SCRATCH"

#=== Création du dossier temporaire sur SCRATCH ================================
TMPDIR_ASTER="${SCRATCH}/aster_${STUDY_NAME}_${SLURM_JOB_ID}"
mkdir -p "$TMPDIR_ASTER" || die "Impossible de créer $TMPDIR_ASTER"
log_info "Dossier tmp   : $TMPDIR_ASTER"

#=== Fonction de nettoyage (appelée en fin de script ou sur erreur) ============
cleanup() {
    local exit_code=$?
    echo ""
    log_info "--- Nettoyage ---"

    # Rapatrier les résultats vers work
    log_info "Rapatriement des résultats vers $WORKDIR/resultats_${STUDY_NAME}/"
    RESULTS_DIR="${WORKDIR}/resultats_${STUDY_NAME}"
    mkdir -p "$RESULTS_DIR"

    # Copier les fichiers de résultats (.rmed, .resu, .mess, .csv, .table, etc.)
    for ext in rmed resu mess csv table txt dat pos msh vtu vtk; do
        find "$TMPDIR_ASTER" -name "*.${ext}" -exec cp -v {} "$RESULTS_DIR/" \; 2>/dev/null
    done

    # Copier les fichiers de résultat nommés REPE_OUT si existant
    if [[ -d "$TMPDIR_ASTER/REPE_OUT" ]]; then
        cp -rv "$TMPDIR_ASTER/REPE_OUT" "$RESULTS_DIR/" 2>/dev/null
    fi

    # Copier le fichier .mess principal s'il existe
    find "$TMPDIR_ASTER" -name "*.mess" -exec cp -v {} "$WORKDIR/" \; 2>/dev/null

    # Suppression du dossier temporaire
    if [[ $KEEP_SCRATCH -eq 0 ]]; then
        log_info "Suppression de $TMPDIR_ASTER"
        rm -rf "$TMPDIR_ASTER"
    else
        log_info "Conservation du dossier scratch (--keep-scratch) : $TMPDIR_ASTER"
    fi

    echo ""
    if [[ $exit_code -eq 0 ]]; then
        log_info "═══ Calcul terminé avec succès ═══"
    else
        log_error "═══ Calcul terminé avec erreur (code=$exit_code) ═══"
    fi
    log_info "Résultats dans : $RESULTS_DIR"
    log_info "Fin : $(date)"
    exit $exit_code
}
trap cleanup EXIT

#=== Copie des fichiers vers SCRATCH ===========================================
log_info "Copie des fichiers vers $TMPDIR_ASTER ..."

cp -v "$COMM_FILE" "$TMPDIR_ASTER/" || die "Échec copie .comm"
cp -v "$MESH_FILE" "$TMPDIR_ASTER/" || die "Échec copie maillage"

if [[ $HAS_EXPORT -eq 1 ]]; then
    cp -v "$EXPORT_FILE" "$TMPDIR_ASTER/"
fi

# Copier les autres fichiers .comm (includes éventuels), .py, .csv, .txt
for ext in py csv txt dat; do
    for f in "$WORKDIR"/*."$ext"; do
        [[ -f "$f" ]] && cp -v "$f" "$TMPDIR_ASTER/"
    done
done

# Copier les fichiers supplémentaires (--extra)
if [[ -n "$EXTRA_FILES" ]]; then
    IFS=',' read -ra EXTRAS <<< "$EXTRA_FILES"
    for f in "${EXTRAS[@]}"; do
        f="$(echo "$f" | xargs)"  # trim
        if [[ -f "$WORKDIR/$f" ]]; then
            cp -v "$WORKDIR/$f" "$TMPDIR_ASTER/"
        elif [[ -f "$f" ]]; then
            cp -v "$f" "$TMPDIR_ASTER/"
        else
            log_warn "Fichier extra introuvable : $f"
        fi
    done
fi

log_info "Copie terminée."
echo ""

#=== Se placer dans le dossier temporaire ======================================
cd "$TMPDIR_ASTER" || die "Impossible de cd vers $TMPDIR_ASTER"

#=== Détection de Code_Aster ==================================================
ASTER_CMD=""

# Priorité 1 : as_run (installation classique)
if command -v as_run &>/dev/null; then
    ASTER_CMD="as_run"
# Priorité 2 : run_aster (Singularity / conteneur)
elif command -v run_aster &>/dev/null; then
    ASTER_CMD="run_aster"
# Priorité 3 : module environment
elif command -v module &>/dev/null; then
    ASTER_MODULE="${ASTER_VERSION:-aster}"
    module load "$ASTER_MODULE" 2>/dev/null
    if command -v as_run &>/dev/null; then
        ASTER_CMD="as_run"
    elif command -v run_aster &>/dev/null; then
        ASTER_CMD="run_aster"
    fi
fi

[[ -n "$ASTER_CMD" ]] || die "Code_Aster introuvable. Chargez le module ou vérifiez l'installation."
log_info "Code_Aster    : $ASTER_CMD ($(which $ASTER_CMD))"

#=== Génération automatique du fichier .export si absent =======================
COMM_BASENAME="$(basename "$COMM_FILE")"
MESH_BASENAME="$(basename "$MESH_FILE")"
MESH_EXT="${MESH_BASENAME##*.}"

if [[ $HAS_EXPORT -eq 0 ]]; then
    log_info "Pas de fichier .export trouvé → génération automatique"

    EXPORT_AUTO="${TMPDIR_ASTER}/${STUDY_NAME}.export"

    # Déterminer l'unité logique du maillage selon le format
    case "$MESH_EXT" in
        med|mmed)  MESH_UNIT=20 ; MESH_TYPE="libaster" ;;
        mail)      MESH_UNIT=20 ; MESH_TYPE="libaster" ;;
        mgib)      MESH_UNIT=19 ; MESH_TYPE="libaster" ;;
        unv)       MESH_UNIT=20 ; MESH_TYPE="libaster" ;;
        *)         MESH_UNIT=20 ; MESH_TYPE="libaster" ;;
    esac

    # Mémoire en Mo (retirer le G/M du paramètre)
    MEM_NUM=$(echo "$MEMORY" | grep -oP '\d+')
    MEM_UNIT=$(echo "$MEMORY" | grep -oP '[A-Za-z]+')
    case "$MEM_UNIT" in
        G|g|GB|Gb) MEM_MB=$((MEM_NUM * 1024)) ;;
        M|m|MB|Mb) MEM_MB=$MEM_NUM ;;
        *)         MEM_MB=$((MEM_NUM * 1024)) ;;
    esac
    # Laisser un peu de marge pour le système
    ASTER_MEM_MB=$(( MEM_MB - 512 ))
    [[ $ASTER_MEM_MB -lt 512 ]] && ASTER_MEM_MB=512

    # Temps en secondes
    IFS=':' read -r T_H T_M T_S <<< "$TIME"
    TIME_SEC=$(( 10#$T_H * 3600 + 10#$T_M * 60 + 10#$T_S ))
    ASTER_TIME_SEC=$(( TIME_SEC - 120 ))  # marge de 2 min
    [[ $ASTER_TIME_SEC -lt 60 ]] && ASTER_TIME_SEC=60

    cat > "$EXPORT_AUTO" <<EXPORT_EOF
P actions make_etude
P version ${ASTER_VERSION:-stable}
P nomjob ${STUDY_NAME}
P debug nodebug
P mode interactif
P ncpus ${NCPUS}
P mpi_nbcpu 1
P mpi_nbnoeud 1
P memjob ${ASTER_MEM_MB}
P tpmax ${ASTER_TIME_SEC}
A memjeveux $((ASTER_MEM_MB / 4)).0
F comm ${TMPDIR_ASTER}/${COMM_BASENAME} D 1
F mmed ${TMPDIR_ASTER}/${MESH_BASENAME} D ${MESH_UNIT}
F mess ${TMPDIR_ASTER}/${STUDY_NAME}.mess R 6
F resu ${TMPDIR_ASTER}/${STUDY_NAME}.resu R 8
F rmed ${TMPDIR_ASTER}/${STUDY_NAME}.rmed R 80
R ${TMPDIR_ASTER}/REPE_OUT R 0
EXPORT_EOF

    EXPORT_FILE="$EXPORT_AUTO"
    log_info "Fichier .export généré : $EXPORT_FILE"
fi

#=== Lancement du calcul =======================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║  Lancement Code_Aster                                              ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  Étude    : $STUDY_NAME"
echo "║  Comm     : $COMM_BASENAME"
echo "║  Maillage : $MESH_BASENAME"
echo "║  CPUs     : $NCPUS"
echo "║  Mémoire  : $MEMORY"
echo "║  Temps    : $TIME"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

log_info "Début du calcul : $(date)"

# Lancement avec as_run ou run_aster
if [[ "$ASTER_CMD" == "as_run" ]]; then
    as_run "$EXPORT_FILE" 2>&1
    ASTER_EXIT=$?
elif [[ "$ASTER_CMD" == "run_aster" ]]; then
    run_aster "$EXPORT_FILE" 2>&1
    ASTER_EXIT=$?
fi

echo ""
log_info "Fin du calcul : $(date)"

#=== Vérification du résultat ==================================================
if [[ -f "${TMPDIR_ASTER}/${STUDY_NAME}.mess" ]]; then
    echo ""
    log_info "--- Dernières lignes du .mess ---"
    tail -20 "${TMPDIR_ASTER}/${STUDY_NAME}.mess"
    echo ""

    # Chercher le diagnostic
    if grep -q "NOOK" "${TMPDIR_ASTER}/${STUDY_NAME}.mess"; then
        log_error "Le calcul a produit des alarmes NOOK"
    fi
    if grep -q "<S>" "${TMPDIR_ASTER}/${STUDY_NAME}.mess"; then
        log_error "Le calcul a produit des erreurs fatales <S>"
        ASTER_EXIT=1
    fi
    if grep -q "EXECUTION_CODE_ASTER_EXIT_.*=0" "${TMPDIR_ASTER}/${STUDY_NAME}.mess" 2>/dev/null; then
        log_info "Code_Aster : exécution OK"
    fi
fi

exit $ASTER_EXIT

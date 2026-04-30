#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  lib/exec.sh — Phase 2 : exécution sur le nœud de calcul
#
#  Appelé automatiquement par sbatch via la variable __RUN_PHASE=EXEC.
#  Ne pas exécuter directement.
#
#  Variables d'environnement attendues (injectées par sbatch --export) :
#    __STUDY_DIR, __STUDY_NAME, __SCRATCH, __EXPORT
#    __ASTER_ROOT, __MODULE, __KEEP_SCRATCH, __DEBUG
#
#  Dépend de : conf/config.sh (COLLECT_EXTENSIONS)
# ══════════════════════════════════════════════════════════════════

set -uo pipefail
[ "${__DEBUG:-0}" = "1" ] && set -x

ALREADY_COLLECTED=0

_cp()      { if command -v rsync &>/dev/null; then rsync -a "$@"; else cp -a "$@"; fi; }
_log_dir() { ls -la "$1" 2>/dev/null | while IFS= read -r l; do log "  $l"; done; }

# ── Rapatriement des résultats ────────────────────────────────────
collect_results() {
    [ "$ALREADY_COLLECTED" -eq 1 ] && return
    ALREADY_COLLECTED=1
    header "RAPATRIEMENT"

    local dest="${__STUDY_DIR}/run_${SLURM_JOB_ID}"
    mkdir -p "$dest" || { log "!! Impossible de créer $dest"; return; }
    local count=0

    log "Fichiers dans le scratch :"
    _log_dir "${__SCRATCH}/"

    _copy_if_exists() {
        local f="$1"
        [ -f "$f" ] && [ -s "$f" ] || return 0
        _cp "$f" "$dest/" && log "  -> $(basename "$f")" || log "  !! ÉCHEC : $(basename "$f")"
        count=$((count + 1))
    }

    # Extensions configurées dans conf/config.sh
    shopt -s nullglob
    for ext in "${COLLECT_EXTENSIONS[@]}"; do
        for f in "${__SCRATCH}"/*."${ext}"; do _copy_if_exists "$f"; done
    done
    # Fichiers de base (POURSUITE)
    for f in "${__SCRATCH}"/glob.* "${__SCRATCH}"/pick.* "${__SCRATCH}"/vola.*; do
        _copy_if_exists "$f"
    done
    shopt -u nullglob

    # Répertoire REPE_OUT (Code_Aster)
    if [ -d "${__SCRATCH}/REPE_OUT" ]; then
        _cp "${__SCRATCH}/REPE_OUT" "$dest/" && log "  -> REPE_OUT/"
        count=$((count + 1))
    fi

    # Lien symbolique latest
    rm -f "${__STUDY_DIR}/latest" 2>/dev/null
    ln -s "run_${SLURM_JOB_ID}" "${__STUDY_DIR}/latest" 2>/dev/null

    log "$count fichier(s) rapatrié(s) -> $dest"
    _log_dir "$dest/"

    if [ "${__KEEP_SCRATCH:-0}" != "1" ]; then
        rm -rf "$__SCRATCH" 2>/dev/null && log "Scratch supprimé"
    else
        log "Scratch conservé : $__SCRATCH"
    fi
}

trap collect_results EXIT
trap 'collect_results; exit 143' SIGTERM

# ── Infos de démarrage ────────────────────────────────────────────
header "CODE_ASTER — $(date)"
log "Job       : $SLURM_JOB_ID"
log "Nœud      : $SLURM_NODELIST"
log "Scratch   : $__SCRATCH"

# ── Chargement du module ──────────────────────────────────────────
if [ -n "${__MODULE:-}" ]; then
    if ! command -v module &>/dev/null; then
        for _mfile in /etc/profile.d/modules.sh /etc/profile.d/lmod.sh; do
            [ -f "$_mfile" ] && . "$_mfile" && break
        done
    fi
    if command -v module &>/dev/null; then
        module load "$__MODULE" 2>&1 && log "Module '$__MODULE' chargé" || warn "Module '$__MODULE' échec"
    else
        warn "Commande module introuvable"
    fi
fi

# ── Recherche de l'exécutable Code_Aster ─────────────────────────
EXE=""
for c in "${__ASTER_ROOT}/bin/run_aster" \
         "${__ASTER_ROOT}/bin/as_run" \
         "$(command -v run_aster 2>/dev/null || true)" \
         "$(command -v as_run   2>/dev/null || true)"; do
    [ -n "$c" ] && [ -x "$c" ] && { EXE="$c"; break; }
done
[ -z "$EXE" ] && { log "ERREUR : Code_Aster introuvable dans $__ASTER_ROOT"; exit 1; }
log "Exécutable : $EXE"
"$EXE" --version 2>&1 | head -1 | while read -r l; do log "Version : $l"; done

# ── Vérification pré-calcul ───────────────────────────────────────
header "VÉRIFICATION"
log "Contenu scratch :"
_log_dir "$__SCRATCH/"
log "Contenu .export :"
while IFS= read -r l; do log "  $l"; done < "$__EXPORT"

# ── Calcul ────────────────────────────────────────────────────────
header "CALCUL"
log "Lancement : $(date)"
RC=0; set +e; "$EXE" "$__EXPORT"; RC=$?; set -e
log "Terminé   : $(date) — code retour $RC"

# ── Diagnostic du .mess ───────────────────────────────────────────
_diagnose_mess() {
    local mess_file="$1"
    [ -f "$mess_file" ] || { log "!! Pas de .mess"; return 1; }
    local na nf ns
    na=$(grep -c "<A>" "$mess_file" 2>/dev/null || true)
    nf=$(grep -c "<F>" "$mess_file" 2>/dev/null || true)
    ns=$(grep -c "<S>" "$mess_file" 2>/dev/null || true)
    log "Alarmes <A>:$na  Fatales <F>:$nf  Exceptions <S>:$ns"
    [ "$nf" -gt 0 ] && grep -B2 -A5 "<F>" "$mess_file" | head -20
    [ "$ns" -gt 0 ] && [ "$nf" -eq 0 ] && grep -B2 -A5 "<S>" "$mess_file" | head -20
    [ "$nf" -gt 0 ] && return 1 || return 0
}

header "DIAGNOSTIC"
_diagnose_mess "${__SCRATCH}/${__STUDY_NAME}.mess" || _log_dir "$__SCRATCH/"
log "Contenu scratch après calcul :"
_log_dir "$__SCRATCH/"

collect_results
header "FIN"
[ "$RC" -eq 0 ] && log "SUCCÈS" || log "ÉCHEC (code $RC)"
log "Résultats : ${__STUDY_DIR}/run_${SLURM_JOB_ID}"
exit $RC

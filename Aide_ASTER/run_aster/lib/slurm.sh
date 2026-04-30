#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  lib/slurm.sh — Soumission sbatch et suivi de job
#
#  Dépend de : lib/ui.sh
# ══════════════════════════════════════════════════════════════════

# soumettre_job SELF STUDY_DIR STUDY_NAME SCRATCH EXPORT
#               ASTER_ROOT ASTER_MODULE PARTITION NODES NTASKS
#               CPUS MEM TIME_LIMIT KEEP_SCRATCH DEBUG DRY_RUN
#
#   Construit et exécute la commande sbatch.
#   En DRY_RUN=1, affiche la commande sans la lancer.
#   Retourne le JOB_ID dans la variable globale _JOB_ID.
soumettre_job() {
    local self="$1"       study_dir="$2"   study_name="$3"
    local scratch="$4"    export_f="$5"    aster_root="$6"
    local aster_mod="$7"  partition="$8"   nodes="$9"
    local ntasks="${10}"  cpus="${11}"      mem="${12}"
    local time_limit="${13}" keep_scratch="${14}" debug="${15}" dry_run="${16}"

    local vars="ALL,__RUN_PHASE=EXEC,__STUDY_DIR=${study_dir},__STUDY_NAME=${study_name}"
    vars+=",__SCRATCH=${scratch},__EXPORT=${export_f},__ASTER_ROOT=${aster_root}"
    vars+=",__MODULE=${aster_mod},__KEEP_SCRATCH=${keep_scratch},__DEBUG=${debug}"

    local -a cmd=(sbatch --parsable
        --job-name="aster_${study_name}"
        --partition="$partition"
        --nodes="$nodes"
        --ntasks="$ntasks"
        --cpus-per-task="$cpus"
        --mem="$mem"
        --time="$time_limit"
        --output="${study_dir}/aster_run_%j.out"
        --error="${study_dir}/aster_run_%j.err"
        --export="$vars"
        "$self"
    )

    if [ "$dry_run" = "1" ]; then
        section "DRY RUN — commande sbatch (non lancée)"
        echo "  ${cmd[*]}"
        echo ""
        info "Contenu du .export généré :"
        while IFS= read -r line; do info "  $line"; done < "$export_f"
        return 0
    fi

    _JOB_ID=$("${cmd[@]}") || { err "sbatch a échoué"; return 1; }
    [ -z "$_JOB_ID" ] && { err "Job ID vide"; return 1; }

    echo "" >/dev/tty
    echo -e "  ${GREEN}${BOLD}✔  Job ${_JOB_ID} soumis avec succès${NC}" >/dev/tty
    echo "" >/dev/tty
    echo -e "  ${DIM}Commandes utiles :${NC}" >/dev/tty
    echo "    squeue -j $_JOB_ID                          # État du job"   >/dev/tty
    echo "    tail -f ${study_dir}/aster_run_${_JOB_ID}.out" >/dev/tty
    echo "    scancel $_JOB_ID                            # Annuler"       >/dev/tty
    echo "    ls ${study_dir}/run_${_JOB_ID}/             # Résultats"     >/dev/tty
    echo "" >/dev/tty
}

# suivre_job JOB_ID LOG_FILE STUDY_DIR
#   Affiche l'état du job et les logs en temps réel (optionnel).
suivre_job() {
    local job="$1" logfile="$2" study_dir="$3"
    local state="" spinner_idx=0
    local -a SP=('|' '/' '-' '\')

    echo ""
    while true; do
        state=$(squeue -j "$job" -h -o "%T" 2>/dev/null || true)
        [ -z "$state" ] && break
        if [ "$state" = "RUNNING" ]; then
            printf "\r  %-70s\n" "État : RUNNING"; break
        fi
        printf "\r  %s  %-12s  %s" "${SP[$spinner_idx]}" "$state" "(Ctrl+C pour détacher)"
        spinner_idx=$(( (spinner_idx+1) % 4 ))
        sleep 3
    done

    if [ "$state" = "RUNNING" ]; then
        info "Logs en temps réel — Ctrl+C pour détacher :"
        echo ""
        local t=0
        while ! [ -f "$logfile" ] && [ "$t" -lt 30 ]; do sleep 1; t=$((t + 1)); done

        if ! squeue -j "$job" -h &>/dev/null; then
            [ -f "$logfile" ] && cat "$logfile" || warn "Fichier log introuvable : $logfile"
        else
            [ -f "$logfile" ] || warn "Fichier log introuvable : $logfile"
            tail -f "$logfile" &
            local TAIL_PID=$!
            # shellcheck disable=SC2064
            trap "kill $TAIL_PID 2>/dev/null; echo ''; info 'Détaché — job $job toujours en cours'; exit 0" INT
            while squeue -j "$job" -h &>/dev/null; do sleep 5; done
            sleep 2; kill $TAIL_PID 2>/dev/null; wait $TAIL_PID 2>/dev/null; trap - INT
        fi
    fi

    # Bilan final
    local dest="${study_dir}/run_${job}"
    echo ""; section "BILAN JOB $job"
    if [ -d "$dest" ]; then
        local mess
        mess=$(ls "${dest}"/*.mess 2>/dev/null | head -1 || true)
        if [ -n "$mess" ]; then
            local na nf ns
            na=$(grep -c "<A>" "$mess" 2>/dev/null || true)
            nf=$(grep -c "<F>" "$mess" 2>/dev/null || true)
            ns=$(grep -c "<S>" "$mess" 2>/dev/null || true)
            if [ "$nf" -eq 0 ] && [ "$ns" -eq 0 ]; then
                ok "Calcul terminé — $na alarme(s)"
            else
                err "Calcul en échec — <F>:$nf  <S>:$ns  <A>:$na"
                [ "$nf" -gt 0 ] && grep -B2 -A5 "<F>" "$mess" | head -20
            fi
        fi
        ok "Résultats : $dest"
        ls "$dest/" 2>/dev/null | while read -r f; do info "  $f"; done
    else
        warn "Dossier de résultats absent : $dest"
    fi
}

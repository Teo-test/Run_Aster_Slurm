#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  lib/export.sh — Validation TYPE/UNITE et génération du .export
#
#  Dépend de : lib/ui.sh (pour warn / err / ok / info)
#
#  Conventions Code_Aster rappelées ici :
#    TYPE    UNITE   Sens
#    ------  ------  ─────────────────────────────
#    comm      1     Fichier de commandes (D)
#    mmed/mail 20    Maillage             (D)
#    mess      6     Messages             (R)
#    resu      8     Résultats texte      (R)
#    rmed     80-99  Résultats MED        (R)
# ══════════════════════════════════════════════════════════════════

# _validate_export_line TYPE UNITE
#   Retourne 1 si la combinaison est clairement incohérente (erreur fatale).
_validate_export_line() {
    local type="$1" unite="$2"
    local ok_flag=0

    case "$type" in
        comm)
            [ "$unite" -ne 1 ] && warn "TYPE 'comm' utilise normalement UNITE=1 (fournie : $unite)" ;;
        mmed|mail)
            [ "$unite" -ne 20 ] && warn "TYPE '$type' utilise normalement UNITE=20 (fournie : $unite)" ;;
        mess)
            if [ "$unite" -ne 6 ]; then
                err "TYPE 'mess' DOIT utiliser UNITE=6 — UNITE=$unite est invalide"
                ok_flag=1
            fi ;;
        resu)
            if [ "$unite" -ne 8 ]; then
                if [ "$unite" -ge 80 ] && [ "$unite" -le 99 ]; then
                    err "TYPE 'resu' avec UNITE=$unite ressemble à une confusion avec 'rmed' (UNITE≥80)"
                    ok_flag=1
                else
                    warn "TYPE 'resu' utilise normalement UNITE=8 (fournie : $unite)"
                fi
            fi ;;
        rmed)
            if [ "$unite" -lt 80 ]; then
                err "TYPE 'rmed' nécessite UNITE>=80 — UNITE=$unite est invalide"
                ok_flag=1
            fi ;;
        libr) : ;;  # pas de convention stricte
        *)
            case "$unite" in
                1)  warn "UNITE=1 est réservée à 'comm' — TYPE '$type' risque un conflit" ;;
                6)  warn "UNITE=6 est réservée à 'mess' — TYPE '$type' risque un conflit" ;;
                8)  warn "UNITE=8 est réservée à 'resu' — TYPE '$type' risque un conflit" ;;
                20) warn "UNITE=20 est réservée à 'mmed/mail' — TYPE '$type' risque un conflit" ;;
            esac ;;
    esac

    case "$unite" in
        1)  [ "$type" != "comm" ]              && { err "UNITE=1 réservée à 'comm', pas à '$type'"; ok_flag=1; } ;;
        6)  [ "$type" != "mess" ]              && { err "UNITE=6 réservée à 'mess', pas à '$type'"; ok_flag=1; } ;;
        8)  [ "$type" != "resu" ]              && { err "UNITE=8 réservée à 'resu', pas à '$type' (pour MED, utiliser rmed + UNITE≥80)"; ok_flag=1; } ;;
        20) [[ "$type" != "mmed" && "$type" != "mail" ]] && warn "UNITE=20 normalement réservée au maillage, pas à '$type'" ;;
    esac

    return "$ok_flag"
}

# _write_export_line EXPORT_FILE keyword type path dir unite
#   Écrit une ligne dans le .export et valide TYPE/UNITE.
#   Incrémente le compteur global _export_errors si nécessaire.
_write_export_line() {
    local export_file="$1" keyword="$2" type="$3" path="$4" dir="$5" unite="$6"

    echo "${keyword} ${type} ${path} ${dir} ${unite}" >> "$export_file"

    if [ "$keyword" = "F" ]; then
        if ! _validate_export_line "$type" "$unite" >/dev/tty 2>&1; then
            _export_errors=$(( _export_errors + 1 ))
        fi
    fi
}

# generer_export EXPORT_FILE SCRATCH STUDY_NAME COMM MED MAIL
#               RESULTS TIME_LIMIT MEM NTASKS
#
#   Génère le fichier .export complet dans EXPORT_FILE.
#   Retourne 1 si des erreurs TYPE/UNITE ont été détectées.
generer_export() {
    local export_file="$1" scratch="$2" study_name="$3"
    local comm="$4" med="$5" mail="$6" results="$7"
    local time_limit="$8" mem="$9" ntasks="${10}"

    _export_errors=0

    # ── Conversion mémoire → MB ──────────────────────────────────
    local mem_mb
    mem_mb=$(echo "$mem" | awk '
        tolower($0) ~ /g$/ { gsub(/[gGiI]/,""); print int($0*1024); next }
        tolower($0) ~ /m$/ { gsub(/[mMiI]/,""); print int($0);      next }
        /^[0-9]+$/          { print int($0); next }
        { print -1 }')
    [ "$mem_mb" -le 0 ] && { err "Mémoire invalide : $mem"; return 1; }
    local aster_mem=$(( mem_mb - 512 ))
    if   [ "$aster_mem" -lt 512  ]; then aster_mem=512; warn "Mémoire très limitée — Aster fixé au minimum (512 MB)"
    elif [ "$aster_mem" -lt 1024 ]; then warn "Mémoire Aster faible (${aster_mem} MB) — risque pour les gros modèles"
    fi

    # ── Conversion durée → secondes ──────────────────────────────
    local time_sec
    time_sec=$(echo "$time_limit" | awk -F'[-:]' '
        NF==4 {print $1*86400+$2*3600+$3*60+$4; next}
        NF==3 {print $1*3600+$2*60+$3;          next}
        NF==2 {print $1*60+$2;                  next}
        {print $1*60}')

    # ── Écriture du .export ───────────────────────────────────────
    : > "$export_file"   # vide/crée le fichier

    {
        echo "P time_limit $time_sec"
        echo "P memory_limit $aster_mem"
        echo "P ncpus $ntasks"
    } >> "$export_file"

    _write_export_line "$export_file" F comm  "${scratch}/$(basename "$comm")"            D 1
    [ -n "$med"  ] && _write_export_line "$export_file" F mmed "${scratch}/$(basename "$med")"  D 20
    [ -n "$mail" ] && _write_export_line "$export_file" F mail "${scratch}/$(basename "$mail")" D 20

    _write_export_line "$export_file" F mess "${scratch}/${study_name}.mess" R 6
    _write_export_line "$export_file" F resu "${scratch}/${study_name}.resu" R 8
    _write_export_line "$export_file" F rmed "${scratch}/${study_name}_resu.rmed" R 80

    # ── Sorties supplémentaires ───────────────────────────────────
    if [ -n "$results" ]; then
        IFS=',' read -ra items <<< "${results// /}"
        for item in "${items[@]}"; do
            local t="${item%%:*}" u="${item##*:}"
            _write_export_line "$export_file" F "$t" "${scratch}/${study_name}_u${u}.${t}" R "$u"
        done
    fi

    if [ "$_export_errors" -gt 0 ]; then
        err "$_export_errors erreur(s) TYPE/UNITE dans le .export — soumission annulée"
        return 1
    fi
    return 0
}

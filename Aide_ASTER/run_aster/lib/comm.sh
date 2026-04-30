#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  lib/comm.sh — Analyse et validation du fichier .comm
#
#  Dépend de : lib/ui.sh, lib/export.sh (_validate_export_line)
# ══════════════════════════════════════════════════════════════════

# Tableau global rempli par _parse_comm_outputs
_COMM_OUTPUTS=()

# _flatten_comm FICHIER
#   Aplatit le .comm en supprimant commentaires et sauts de ligne
#   au sein d'un appel de fonction (équilibre des parenthèses).
_flatten_comm() {
    awk '
    BEGIN { buf=""; depth=0 }
    /^[[:space:]]*#/ { next }
    {
        line = $0; gsub(/#.*$/, "", line)
        buf = buf " " line
        for (i=1; i<=length(line); i++) {
            c = substr(line, i, 1)
            if      (c == "(") depth++
            else if (c == ")") depth--
        }
        if (depth <= 0 && buf ~ /[^[:space:]]/) {
            print buf; buf = ""; depth = 0
        }
    }
    END { if (buf ~ /[^[:space:]]/) print buf }
    ' "$1" 2>/dev/null
}

# _unite_to_canonical_type UNITE INSTRUCTION FORMAT EXT
#   Déduit le TYPE canonique du .export à partir de l'UNITE et du contexte.
#   Écrit les avertissements de cohérence sur stderr.
_unite_to_canonical_type() {
    local unite="$1" instr="$2" fmt="$3" ext="$4"
    local type="" warn_msg=""

    # 1. UNITEs strictement réservées
    case "$unite" in
        1)  type="comm" ;;
        6)  type="mess" ;;
        8)  type="resu" ;;
        20) type="mmed"; warn_msg="UNITE=20 réservée au maillage (D) — sortie sur cette UNITE inhabituelle" ;;
    esac

    # 2. UNITE ≥ 80 → rmed par convention
    if [ -z "$type" ] && [ "$unite" -ge 80 ]; then
        type="rmed"
        [ "$instr" = "IMPR_RESU" ] && [ "$fmt" != "MED" ] && \
            warn_msg="IMPR_RESU sans FORMAT=MED sur UNITE=$unite (≥80 → rmed attendu) — FORMAT=MED manquant ?"
    fi

    # 3. Déduction depuis l'instruction Aster
    if [ -z "$type" ]; then
        case "$instr" in
            IMPR_RESU)
                if [ "$fmt" = "MED" ]; then
                    type="rmed"
                    [ "$unite" -lt 80 ] && warn_msg="IMPR_RESU FORMAT=MED (→ rmed) sur UNITE=$unite — UNITE devrait être ≥80"
                else
                    type="resu"
                    [ "$unite" -ne 8 ] && warn_msg="IMPR_RESU texte (→ resu) sur UNITE=$unite — UNITE devrait être 8"
                fi ;;
            IMPR_TABLE)  type="table" ;;
            DEFI_FICHIER) type="${ext:-dat}" ;;
            *)            type="dat" ;;
        esac
    fi

    echo "$type"
    [ -n "$warn_msg" ] && echo "$warn_msg" >&2
}

# _parse_comm_outputs FICHIER_COMM
#   Remplit _COMM_OUTPUTS avec des entrées "LABEL|TYPE|UNITE"
#   pour chaque sortie non standard détectée dans le .comm.
_parse_comm_outputs() {
    local comm_file="$1"
    _COMM_OUTPUTS=()
    local flat
    flat=$(_flatten_comm "$comm_file")

    while IFS= read -r block; do
        [ -z "$block" ] && continue

        local unite
        unite=$(echo "$block" | sed -n 's/.*UNITE[[:space:]]*=[[:space:]]*\([0-9]\+\).*/\1/p' | head -1)
        [ -z "$unite" ] && continue
        case "$unite" in 1|20) continue ;; esac

        local instr=""
        for _kw in IMPR_RESU IMPR_TABLE DEFI_FICHIER; do
            echo "$block" | grep -q "$_kw" && { instr="$_kw"; break; }
        done
        [ -z "$instr" ] && continue

        local fmt=""
        echo "$block" | grep -qE "FORMAT[[:space:]]*=[[:space:]]*['\"]?MED['\"]?" && fmt="MED"

        local ext=""
        [ "$instr" = "DEFI_FICHIER" ] && \
            ext=$(echo "$block" | \
                  sed -n "s/.*FICHIER[[:space:]]*=[[:space:]]*['\"][^'\"]*\.\([a-zA-Z0-9]*\)['\"].*/\1/p" \
                  | head -1)

        local type warn_out
        warn_out=$( _unite_to_canonical_type "$unite" "$instr" "$fmt" "$ext" 2>&1 >/dev/null )
        type=$(      _unite_to_canonical_type "$unite" "$instr" "$fmt" "$ext" 2>/dev/null )
        [ -n "$warn_out" ] && warn "$warn_out" >/dev/tty

        local label
        case "$instr" in
            IMPR_RESU)
                [ "$fmt" = "MED" ] \
                    && label="IMPR_RESU FORMAT=MED  →  unite $unite  (type: $type)" \
                    || label="IMPR_RESU texte       →  unite $unite  (type: $type)" ;;
            IMPR_TABLE)  label="IMPR_TABLE            →  unite $unite  (type: $type)" ;;
            DEFI_FICHIER) label="DEFI_FICHIER          →  unite $unite  (type: $type${ext:+  ext: .$ext})" ;;
        esac

        _COMM_OUTPUTS+=("${label}|${type}|${unite}")
    done <<< "$flat"
}

# valider_comm COMM STUDY_DIR MED MAIL RESULTS
#   Vérifie la cohérence du .comm avec les fichiers présents.
#   Retourne 1 si des erreurs bloquantes sont détectées.
valider_comm() {
    local comm_file="$1" study_dir="$2" has_med="$3" has_mail="$4" results="$5"
    local errors=0 flat
    flat=$(_flatten_comm "$comm_file")

    section "Validation du .comm"

    # LIRE_MAILLAGE → maillage requis
    if echo "$flat" | grep -q "LIRE_MAILLAGE"; then
        if [ -z "$has_med" ] && [ -z "$has_mail" ]; then
            err "LIRE_MAILLAGE détecté mais aucun fichier .med ou .mail présent"
            errors=$((errors + 1))
        else
            ok "LIRE_MAILLAGE : maillage détecté"
        fi
    fi

    # POURSUITE → base requise
    if echo "$flat" | grep -q "POURSUITE"; then
        local -a bases=()
        shopt -s nullglob
        bases=("${study_dir}"/glob.* "${study_dir}"/pick.*)
        shopt -u nullglob
        if [ ${#bases[@]} -eq 0 ]; then
            warn "POURSUITE détecté mais aucune base (glob.*/pick.*) trouvée dans $study_dir"
            warn "  → Spécifiez le dossier base à l'étape suivante."
        else
            ok "POURSUITE : base trouvée (${#bases[@]} fichiers)"
        fi
    fi

    # Vérification UNITE déclarées vs RESULTS
    local -a all_unites=() all_types=()
    for _entry in "${_COMM_OUTPUTS[@]}"; do
        local _t="${_entry#*|}"; _t="${_t%%|*}"
        local _u="${_entry##*|}"
        all_types+=("$_t"); all_unites+=("$_u")
    done

    local declared_unites=""
    [ -n "$results" ] && declared_unites=$(echo "$results" | tr ',' '\n' | sed 's/.*://')

    for i in "${!all_unites[@]}"; do
        local _mu="${all_unites[$i]}"
        if ! echo "$declared_unites" | grep -qw "$_mu"; then
            warn "UNITE=$_mu  type attendu: ${all_types[$i]} — non déclarée dans RESULTS"
            warn "  → Ce fichier de sortie sera perdu après le calcul !"
        fi
    done

    # INCLUDEs
    local includes
    includes=$(echo "$flat" | grep -oP "INCLUDE\s*\(.*?DONNEE\s*=\s*['\"]([^'\"]+)['\"]" | \
               sed -n "s/.*['\"]\\([^'\"]*\\)['\"].*/\\1/p" 2>/dev/null || true)
    while IFS= read -r inc; do
        [ -z "$inc" ] && continue
        if [ ! -f "${study_dir}/${inc}" ]; then
            warn "INCLUDE '${inc}' — fichier absent de ${study_dir}"
        else
            ok "INCLUDE : ${inc} présent"
        fi
    done <<< "$includes"

    # Présence de DEBUT/POURSUITE et FIN
    echo "$flat" | grep -qE "^\s*(DEBUT|POURSUITE)\s*\(" || warn "Ni DEBUT() ni POURSUITE() trouvé — fichier incomplet ?"
    echo "$flat" | grep -qE "^\s*FIN\s*\(\s*\)"          || warn "FIN() absent — le calcul risque de ne pas terminer proprement"

    [ "$errors" -gt 0 ] && return 1
    return 0
}

#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  lib/utils.sh — Utilitaires génériques
#
#  Sourcé par run_aster.sh (phase 1).
#  Aucune dépendance externe.
# ══════════════════════════════════════════════════════════════════

# _find_first DIR PATTERN
#   Retourne le premier fichier correspondant au pattern dans DIR.
#   Avertit si plusieurs fichiers correspondent.
_find_first() {
    local dir="$1" pattern="$2"
    local -a arr=()
    shopt -s nullglob; arr=("${dir}"/${pattern}); shopt -u nullglob
    [ ${#arr[@]} -ge 1 ] && echo "${arr[0]}"
    [ ${#arr[@]} -gt 1 ] && warn "Plusieurs ${pattern} trouvés dans ${dir}, utilisation du premier" >&2
}

# _count_files DIR PATTERN
#   Retourne le nombre de fichiers correspondant au pattern dans DIR.
_count_files() {
    local dir="$1" pattern="$2"
    local -a arr=()
    shopt -s nullglob; arr=("${dir}"/${pattern}); shopt -u nullglob
    echo "${#arr[@]}"
}

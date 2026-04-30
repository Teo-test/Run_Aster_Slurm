#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  lib/ui.sh — Affichage, couleurs et menus interactifs
#
#  Sourcé par run_aster.sh (phase 1 uniquement).
#  Aucune dépendance sur les autres lib/*.sh.
# ══════════════════════════════════════════════════════════════════

# ── Codes couleur ─────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'
BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

# ── Fonctions de log ──────────────────────────────────────────────
info()   { echo -e "  ${BLUE}●${NC}  $*"; }
ok()     { echo -e "  ${GREEN}✔${NC}  $*"; }
warn()   { echo -e "  ${YELLOW}⚠${NC}  $*"; }
err()    { echo -e "  ${RED}✖${NC}  $*" >&2; }
log()    { echo "[$(date +%H:%M:%S)] $*"; }
header() { echo ""; echo "========================================================"; echo "  $*"; echo "========================================================"; }

section() {
    echo "" >/dev/tty
    echo -e "  ${CYAN}${BOLD}── $* ──${NC}" >/dev/tty
}

banner() {
    local w=48
    echo "" >/dev/tty
    echo -e "  ${CYAN}╔$(printf '═%.0s' $(seq 1 $w))╗${NC}" >/dev/tty
    printf "  ${CYAN}║${NC}${BOLD}%-${w}s${NC}${CYAN}║${NC}\n" "  🔧  RUN ASTER — Mode interactif" >/dev/tty
    printf "  ${CYAN}║${NC}${DIM}%-${w}s${NC}${CYAN}║${NC}\n" "  Navigation : ↑↓  sélection : entrée" >/dev/tty
    echo -e "  ${CYAN}╚$(printf '═%.0s' $(seq 1 $w))╝${NC}" >/dev/tty
    echo "" >/dev/tty
}

# ── Barre de progression ──────────────────────────────────────────
_ETAPE_COURANTE=0
_ETAPES=("Dossier" "Fichiers" "Sorties" "Ressources" "Options" "Confirmation")

afficher_progression() {
    local n=${#_ETAPES[@]}
    local bar=""
    for ((i=0; i<n; i++)); do
        if   [ "$i" -lt "$_ETAPE_COURANTE" ]; then bar+="${GREEN}●${NC} "
        elif [ "$i" -eq "$_ETAPE_COURANTE" ]; then bar+="${CYAN}${BOLD}●${NC} "
        else                                        bar+="${DIM}○${NC} "
        fi
    done
    echo -e "\n  ${bar} ${DIM}(${_ETAPES[$_ETAPE_COURANTE]})${NC}" >/dev/tty
}

# ── Navigation clavier ────────────────────────────────────────────
_MENU_IDX=0; _MENU_ITEMS=(); _SAISIE=""; _TOUCHE=""

_lire_touche() {
    local k1 k2 k3
    IFS= read -r -s -n1 k1 </dev/tty
    if [[ "$k1" == $'\x1b' ]]; then
        IFS= read -r -s -n1 -t 0.05 k2 </dev/tty || k2=""
        IFS= read -r -s -n1 -t 0.05 k3 </dev/tty || k3=""
        _TOUCHE="${k1}${k2}${k3}"
    else
        _TOUCHE="$k1"
    fi
}

_dessiner_menu() {
    local sel="$1"; shift; local opts=("$@")
    for ((i=0; i<${#opts[@]}; i++)); do
        if ((i == sel)); then
            printf "    ${CYAN}${BOLD}❯ %-55s${NC}\n" "${opts[$i]}" >/dev/tty
        else
            printf "      %-55s\n" "${opts[$i]}" >/dev/tty
        fi
    done
}

_COCHES=()
_dessiner_cases() {
    local sel="$1"; shift; local opts=("$@"); local i marq
    for ((i=0; i<${#opts[@]}; i++)); do
        [ "$i" -eq "$sel" ] && marq="${CYAN}${BOLD}❯${NC}" || marq=" "
        if [ "${_COCHES[$i]}" = "1" ]; then
            printf "    %b [${GREEN}✔${NC}] %-51s\n" "$marq" "${opts[$i]}" >/dev/tty
        else
            printf "    %b [ ] %-51s\n"               "$marq" "${opts[$i]}" >/dev/tty
        fi
    done
}

menu_fleches() {
    local msg="$1"; shift; local opts=("$@"); local n=${#opts[@]} sel=0
    printf "\n    ${BOLD}%s${NC}\n" "$msg" >/dev/tty
    printf "    ${DIM}(↑↓ : naviguer  —  entrée : valider  —  ctrl+c : étape précédente)${NC}\n" >/dev/tty
    tput civis >/dev/tty 2>/dev/null || true
    _dessiner_menu "$sel" "${opts[@]}"
    while true; do
        _lire_touche
        case "$_TOUCHE" in
            $'\x1b[A') sel=$(( (sel - 1 + n) % n )) ;;
            $'\x1b[B') sel=$(( (sel + 1) % n ))     ;;
            $'\x0d'|$'\x0a'|'') break ;;
            $'\x03') tput cnorm >/dev/tty 2>/dev/null || true
                     printf "    ${DIM}← Étape précédente${NC}\n" >/dev/tty
                     _MENU_IDX=-1; return ;;
        esac
        printf "\033[%dA" "$n" >/dev/tty
        _dessiner_menu "$sel" "${opts[@]}"
    done
    printf "\033[%dA" "$n" >/dev/tty
    for ((i=0; i<n; i++)); do
        if ((i == sel)); then
            printf "    ${GREEN}✔ ${BOLD}%-55s${NC}\n" "${opts[$i]}" >/dev/tty
        else
            printf "\033[2K\r\033[1B" >/dev/tty
        fi
    done
    tput cnorm >/dev/tty 2>/dev/null || true
    _MENU_IDX="$sel"
}

menu_cases() {
    local msg="$1"; shift; local opts=("$@"); local n=${#opts[@]} sel=0 i
    _COCHES=(); for ((i=0; i<n; i++)); do _COCHES[$i]=0; done
    printf "\n    ${BOLD}%s${NC}\n" "$msg" >/dev/tty
    printf "    ${DIM}(espace : cocher  —  a : tout  —  i : inverser  —  entrée : valider  —  ctrl+c : précédent)${NC}\n" >/dev/tty
    tput civis >/dev/tty 2>/dev/null || true
    _MENU_IDX=0
    _dessiner_cases "$sel" "${opts[@]}"
    while true; do
        _lire_touche
        local j
        case "$_TOUCHE" in
            $'\x1b[A') sel=$(( (sel - 1 + n) % n )) ;;
            $'\x1b[B') sel=$(( (sel + 1) % n ))     ;;
            ' ')        _COCHES[$sel]=$(( _COCHES[sel] ^ 1 )) ;;
            'a')        for ((j=0; j<n; j++)); do _COCHES[$j]=1; done ;;
            'i')        for ((j=0; j<n; j++)); do _COCHES[$j]=$(( _COCHES[j] ^ 1 )); done ;;
            $'\x0d'|$'\x0a'|'') break ;;
            $'\x03') tput cnorm >/dev/tty 2>/dev/null || true
                     printf "    ${DIM}← Étape précédente${NC}\n" >/dev/tty
                     _MENU_ITEMS=(); _MENU_IDX=-1; return ;;
        esac
        printf "\033[%dA" "$n" >/dev/tty
        _dessiner_cases "$sel" "${opts[@]}"
    done
    tput cnorm >/dev/tty 2>/dev/null || true
    _MENU_ITEMS=()
    for ((i=0; i<n; i++)); do [ "${_COCHES[$i]}" = "1" ] && _MENU_ITEMS+=("$i"); done
}

saisir() {
    local msg="$1" defaut="${2:-}"
    if [ -n "$defaut" ]; then
        printf "    ${BOLD}%s${NC} [${DIM}%s${NC}] : " "$msg" "$defaut" >/dev/tty
    else
        printf "    ${BOLD}%s${NC} : " "$msg" >/dev/tty
    fi
    IFS= read -r _SAISIE </dev/tty
    [ -z "$_SAISIE" ] && _SAISIE="$defaut"
}

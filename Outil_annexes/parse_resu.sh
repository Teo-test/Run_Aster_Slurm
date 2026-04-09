#!/bin/bash
#===============================================================================
#  parse_resu.sh — Analyse et extraction des fichiers .resu Code_Aster
#===============================================================================
#
#  Usage :  bash parse_resu.sh [OPTIONS] [FICHIER.resu | DOSSIER]
#
#  Sans argument → mode interactif (navigation clavier ↑↓ espace entrée)
#
#  OPTIONS
#  ─────────────────────────────────────────────────────────────────────────
#    -f, --field NOM       Champ à extraire (ex: DEPL, SIEF_ELNO, EQUI_ELNO)
#    -o, --ordre N         Numéro d'ordre cible (defaut : tous)
#    -a, --all             Extraire tous les blocs détectés vers CSV
#        --stats           Afficher statistiques (min/max/moy) sans CSV
#        --csv             Forcer export CSV (un fichier par bloc)
#    -O, --outdir DIR      Dossier de sortie (defaut : dossier du .resu)
#    -q, --quiet           Sortie minimale
#    -h, --help            Afficher cette aide
#
#  LIMITES CONNUES (ébauche v1.0)
#  ─────────────────────────────────────────────────────────────────────────
#    · Colonnes en mode wrapping (>6 composantes) : seul le premier groupe
#      est extrait dans cette version
#    · Format IMPR_TABLE (colonnes libres) : non pris en charge
#    · Blocs CHAM_ELEM sous-point (ELGA SOUS_POINT) : support partiel
#
#  Auteur  : Teo LEROY
#  Version : 1.0
#===============================================================================

# ══════════════════════════════════════════
#  AFFICHAGE
# ══════════════════════════════════════════

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()     { echo -e "${RED}[ ERR]${NC}  $*" >&2; }
section() { echo -e "\n${BOLD}${CYAN}> $*${NC}"; echo -e "${CYAN}$(printf -- '-%.0s' {1..60})${NC}"; }

# ══════════════════════════════════════════
#  NAVIGATION CLAVIER — menus interactifs
#  (identique à run_aster.sh)
# ══════════════════════════════════════════

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
            printf "  ${CYAN}${BOLD}❯ %-55s${NC}\n" "${opts[$i]}" >/dev/tty
        else
            printf "    %-55s\n" "${opts[$i]}" >/dev/tty
        fi
    done
}

_COCHES=()
_dessiner_cases() {
    local sel="$1"; shift; local opts=("$@"); local i marq
    for ((i=0; i<${#opts[@]}; i++)); do
        [ "$i" -eq "$sel" ] && marq="${CYAN}${BOLD}❯${NC}" || marq=" "
        if [ "${_COCHES[$i]}" = "1" ]; then
            printf "  %b [${GREEN}✔${NC}] %-51s\n" "$marq" "${opts[$i]}" >/dev/tty
        else
            printf "  %b [ ] %-51s\n"               "$marq" "${opts[$i]}" >/dev/tty
        fi
    done
}

menu_fleches() {
    local msg="$1"; shift; local opts=("$@"); local n=${#opts[@]} sel=0
    printf "\n${BOLD}  %s${NC}\n" "$msg" >/dev/tty
    tput civis >/dev/tty 2>/dev/null || true
    _dessiner_menu "$sel" "${opts[@]}"
    while true; do
        _lire_touche
        case "$_TOUCHE" in
            $'\x1b[A') sel=$(( (sel - 1 + n) % n )) ;;
            $'\x1b[B') sel=$(( (sel + 1) % n ))     ;;
            $'\x0d'|$'\x0a'|'') break ;;
            $'\x03') tput cnorm >/dev/tty 2>/dev/null || true; printf "\n" >/dev/tty; _MENU_IDX=-1; return ;;
        esac
        printf "\033[%dA" "$n" >/dev/tty
        _dessiner_menu "$sel" "${opts[@]}"
    done
    printf "\033[%dA" "$n" >/dev/tty
    for ((i=0; i<n; i++)); do
        if ((i == sel)); then
            printf "  ${GREEN}✔ ${BOLD}%-55s${NC}\n" "${opts[$i]}" >/dev/tty
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
    printf "\n${BOLD}  %s${NC}\n" "$msg" >/dev/tty
    printf "  ${DIM}(espace : cocher  —  a : tout  —  i : inverser  —  entrée : valider)${NC}\n" >/dev/tty
    tput civis >/dev/tty 2>/dev/null || true
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
            $'\x03') tput cnorm >/dev/tty 2>/dev/null || true; printf "\n" >/dev/tty; _MENU_ITEMS=(); return ;;
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
        printf "  ${BOLD}%s${NC} [${DIM}%s${NC}] : " "$msg" "$defaut" >/dev/tty
    else
        printf "  ${BOLD}%s${NC} : " "$msg" >/dev/tty
    fi
    IFS= read -r _SAISIE </dev/tty
    [ -z "$_SAISIE" ] && _SAISIE="$defaut"
}

# ══════════════════════════════════════════
#  AIDE
# ══════════════════════════════════════════

usage() {
    cat <<'EOF'
USAGE
  bash parse_resu.sh [OPTIONS] [FICHIER.resu | DOSSIER]

FICHIERS
  Sans argument           Mode interactif (détection auto dans le dossier courant)
  FICHIER.resu            Traiter ce fichier directement
  DOSSIER                 Chercher les .resu dans ce dossier

OPTIONS DE FILTRAGE
  -f, --field NOM         Champ à traiter (ex: DEPL, SIEF_ELNO, EQUI_ELNO)
  -o, --ordre N           Numéro d'ordre cible (0 = tous)

ACTIONS
  -a, --all               Exporter tous les blocs en CSV
      --stats             Statistiques min/max/moy (sans export)
      --csv               Export CSV (un fichier par bloc)
  -O, --outdir DIR        Dossier de sortie (defaut : même dossier que le .resu)

OPTIONS
  -q, --quiet             Sortie minimale
  -h, --help              Cette aide

EXEMPLES
  bash parse_resu.sh                             # interactif
  bash parse_resu.sh calcul.resu                 # interactif sur ce fichier
  bash parse_resu.sh -f DEPL --csv calcul.resu   # export CSV du champ DEPL
  bash parse_resu.sh --stats -f SIEF_ELNO calcul.resu
  bash parse_resu.sh --all -O ./resultats/ ./run_12345/
EOF
    exit 0
}

# ══════════════════════════════════════════
#  PARSING DU .resu
# ══════════════════════════════════════════
#
#  Format Code_Aster :
#  ─────────────────────────────────────────────────────────────────
#   ---[ligne de séparateur ≥30 tirets]---
#   CHAMP AUX NOEUDS PAR ELEMENTS DE : DEPL    NUMERO D'ORDRE: N  INST: X.XXE+XX
#   LOCALISATION : NOEU | ELNO | ELGA
#
#   NOEUD    DX       DY       DZ        ← ligne de colonnes
#    N1   1.23E-03  4.56E-04  0.00E+00  ← données
#    N2   ...
#   ---[separator suivant ou EOF]---
# ══════════════════════════════════════════

# Tableaux globaux de blocs
declare -a _BLOCK_FIELD  # nom du champ (DEPL, SIEF_ELNO...)
declare -a _BLOCK_ORDER  # numéro d'ordre
declare -a _BLOCK_INST   # instant (chaîne)
declare -a _BLOCK_LOC    # localisation (NOEU/ELNO/ELGA)
declare -a _BLOCK_HLINE  # numéro de ligne de l'en-tête colonnes
declare -a _BLOCK_DSTART # numéro de ligne du premier enregistrement
_BLOCK_COUNT=0

# _scan_resu FILE
# Remplit les tableaux _BLOCK_* en une passe awk sur le fichier.
_scan_resu() {
    local file="$1"
    _BLOCK_COUNT=0
    _BLOCK_FIELD=(); _BLOCK_ORDER=(); _BLOCK_INST=()
    _BLOCK_LOC=();   _BLOCK_HLINE=(); _BLOCK_DSTART=()

    local raw
    raw=$(awk '
    BEGIN {
        n=0; state=0
        field=""; order="0"; instant="N/A"; loc="NOEU"
        hline=0; dstart=0
    }

    # ── Ligne de séparateur ──────────────────────────────────────
    /^[[:space:]]*-{30,}[[:space:]]*$/ {
        if (state==4 && dstart>0) {
            printf "%d|%s|%s|%s|%s|%d|%d\n", n, field, order, instant, loc, hline, dstart
        }
        state=1
        field=""; order="0"; instant="N/A"; loc="NOEU"; hline=0; dstart=0
        next
    }

    # ── Ligne CHAMP ──────────────────────────────────────────────
    state==1 && /CHAMP/ {
        n++
        tmp=$0
        # Champ : mot après "DE :"
        sub(/.*DE[[:space:]]*:[[:space:]]*/, "", tmp)
        split(tmp, a, " ")
        field=a[1]

        # Ordre : entier après "ORDRE :"
        tmp2=$0
        if (match(tmp2, /ORDRE[[:space:]]*:[[:space:]]*/)) {
            sub(/.*ORDRE[[:space:]]*:[[:space:]]*/, "", tmp2)
            split(tmp2, b, " ")
            order=int(b[1])
        } else { order=0 }

        # Instant : nombre après "INST :"
        tmp3=$0
        if (match(tmp3, /INST[[:space:]]*:[[:space:]]*/)) {
            sub(/.*INST[[:space:]]*:[[:space:]]*/, "", tmp3)
            split(tmp3, c, " ")
            instant=c[1]
        } else { instant="N/A" }

        state=2; next
    }

    # Ligne non-CHAMP juste après séparateur → pas un bloc résultat
    state==1 && !/^[[:space:]]*$/ { state=0; next }
    state==1 { next }

    # ── Ligne LOCALISATION ───────────────────────────────────────
    state==2 && /LOCALISATION/ {
        if      (/NOEU/) loc="NOEU"
        else if (/ELGA/) loc="ELGA"
        else             loc="ELNO"
        next
    }

    # Lignes vides dans entete
    state==2 && /^[[:space:]]*$/ { next }

    # ── En-tête des colonnes (1ère ligne non vide après LOCALISATION) ──
    state==2 { hline=NR; state=3; next }

    # Ligne vide entre en-tête et données
    state==3 && /^[[:space:]]*$/ { next }

    # ── 1ère ligne de données ────────────────────────────────────
    state==3 { dstart=NR; state=4; next }

    # ── Lignes de données ────────────────────────────────────────
    # (ignorées ici, on retient juste dstart)

    END {
        if (state==4 && dstart>0) {
            printf "%d|%s|%s|%s|%s|%d|%d\n", n, field, order, instant, loc, hline, dstart
        }
    }
    ' "$file")

    while IFS='|' read -r idx field order instant loc hline dstart; do
        [ -z "$idx" ] && continue
        local i=$(( idx - 1 ))
        _BLOCK_FIELD[$i]="$field"
        _BLOCK_ORDER[$i]="$order"
        _BLOCK_INST[$i]="$instant"
        _BLOCK_LOC[$i]="$loc"
        _BLOCK_HLINE[$i]="$hline"
        _BLOCK_DSTART[$i]="$dstart"
        _BLOCK_COUNT="$idx"
    done <<< "$raw"
}

# _get_cols FILE HLINE → imprime les noms de colonnes séparés par '|'
_get_cols() {
    local file="$1" hline="$2"
    awk -v h="$hline" 'NR==h { for(i=1;i<=NF;i++) printf "%s%s",$i,(i<NF?"|":""); print ""; exit }' "$file"
}

# _block_label IDX → "DEPL  ordre=1  inst=1.00E+00  [NOEU]"
_block_label() {
    local i="$1"
    printf "%-12s  ordre=%-3s  inst=%-12s  [%s]" \
        "${_BLOCK_FIELD[$i]}" "${_BLOCK_ORDER[$i]}" "${_BLOCK_INST[$i]}" "${_BLOCK_LOC[$i]}"
}

# ══════════════════════════════════════════
#  EXTRACTION CSV
# ══════════════════════════════════════════

# _extract_csv FILE BLOCK_IDX OUT_DIR QUIET
# Crée OUT_DIR/FIELD_ordN_instX.csv avec en-tête + données
_extract_csv() {
    local file="$1" idx="$2" outdir="$3" quiet="${4:-0}"
    local field="${_BLOCK_FIELD[$idx]}"
    local order="${_BLOCK_ORDER[$idx]}"
    local inst="${_BLOCK_INST[$idx]}"
    local loc="${_BLOCK_LOC[$idx]}"
    local hline="${_BLOCK_HLINE[$idx]}"
    local dstart="${_BLOCK_DSTART[$idx]}"

    # Nettoyer l'instant pour le nom de fichier
    local inst_safe
    inst_safe=$(echo "$inst" | tr '.' '_' | tr '+' 'p' | tr '-' 'm')
    local outfile="${outdir}/${field}_ord${order}_inst${inst_safe}.csv"

    awk -v hline="$hline" -v dstart="$dstart" '
    NR == hline {
        # En-tête CSV : colonnes séparées par virgules
        for (i=1; i<=NF; i++) printf "%s%s", $i, (i<NF?",":"")
        print ""
        next
    }
    NR < dstart { next }
    /^[[:space:]]*-{30,}[[:space:]]*$/ { exit }
    /^[[:space:]]*$/ { next }
    {
        # Données : remplacer les espaces multiples par des virgules
        out=""
        for (i=1; i<=NF; i++) out = out $i (i<NF?",":"")
        print out
    }
    ' "$file" > "$outfile"

    local nlines
    nlines=$(awk 'NR>1' "$outfile" | wc -l)
    [ "$quiet" = "0" ] && ok "CSV : $(basename "$outfile")  (${nlines} enregistrement(s))"
    echo "$outfile"
}

# ══════════════════════════════════════════
#  STATISTIQUES
# ══════════════════════════════════════════

# _compute_stats FILE BLOCK_IDX
# Affiche min/max/moy par composante
_compute_stats() {
    local file="$1" idx="$2"
    local field="${_BLOCK_FIELD[$idx]}"
    local order="${_BLOCK_ORDER[$idx]}"
    local inst="${_BLOCK_INST[$idx]}"
    local loc="${_BLOCK_LOC[$idx]}"
    local hline="${_BLOCK_HLINE[$idx]}"
    local dstart="${_BLOCK_DSTART[$idx]}"

    echo ""
    echo -e "  ${BOLD}${field}${NC}  ordre=${order}  inst=${inst}  [${loc}]"
    echo -e "  ${DIM}$(printf -- '-%.0s' {1..56})${NC}"

    awk -v hline="$hline" -v dstart="$dstart" '
    NR == hline {
        for (i=1; i<=NF; i++) cols[i]=$i
        ncols=NF
        # Première colonne numérique : NOEU→2, ELNO→3 (MAILLE+NOEUD), ELGA→3
        first=2
        if (cols[1]=="MAILLE") first=3
        next
    }
    NR < dstart { next }
    /^[[:space:]]*-{30,}[[:space:]]*$/ { exit }
    /^[[:space:]]*$/ { next }
    {
        for (i=first; i<=ncols; i++) {
            v=$i+0
            if (cnt[i]==0) { mn[i]=v; mx[i]=v }
            if (v<mn[i]) mn[i]=v
            if (v>mx[i]) mx[i]=v
            sm[i]+=v; cnt[i]++
        }
    }
    END {
        printf "  %-12s  %14s  %14s  %14s  %8s\n","COMPOSANTE","MIN","MAX","MOY","N"
        printf "  %-12s  %14s  %14s  %14s  %8s\n","──────────","─────────────","─────────────","─────────────","───────"
        for (i=first; i<=ncols; i++) {
            if (cnt[i]>0)
                printf "  %-12s  %+14.6E  %+14.6E  %+14.6E  %8d\n",
                    cols[i], mn[i], mx[i], sm[i]/cnt[i], cnt[i]
        }
    }
    ' "$file"
    echo ""
}

# ══════════════════════════════════════════
#  AFFICHAGE TERMINAL
# ══════════════════════════════════════════

# _display_block FILE BLOCK_IDX [N_LINES]
# Affiche les N premières lignes de données dans le terminal
_display_block() {
    local file="$1" idx="$2" maxlines="${3:-30}"
    local hline="${_BLOCK_HLINE[$idx]}"
    local dstart="${_BLOCK_DSTART[$idx]}"
    local field="${_BLOCK_FIELD[$idx]}"
    local order="${_BLOCK_ORDER[$idx]}"
    local inst="${_BLOCK_INST[$idx]}"

    echo ""
    echo -e "  ${BOLD}${field}${NC}  ordre=${order}  inst=${inst}"
    echo ""

    awk -v hline="$hline" -v dstart="$dstart" -v maxl="$maxlines" '
    NR == hline { print "  " $0; next }
    NR < dstart { next }
    /^[[:space:]]*-{30,}[[:space:]]*$/ { exit }
    /^[[:space:]]*$/ { next }
    {
        if (shown >= maxl) {
            if (shown == maxl) print "  [... tronqué]"
        } else {
            print "  " $0
        }
        shown++
    }
    ' "$file"
    echo ""
}

# ══════════════════════════════════════════
#  RÉSUMÉ DU FICHIER
# ══════════════════════════════════════════

_print_summary() {
    local file="$1"
    echo ""
    info "Fichier : $file"
    info "Blocs   : ${_BLOCK_COUNT}"

    # Champs uniques
    local -A _fields_seen=()
    local i
    for ((i=0; i<_BLOCK_COUNT; i++)); do
        _fields_seen["${_BLOCK_FIELD[$i]}"]=$((${_fields_seen["${_BLOCK_FIELD[$i]}"]-0}+1))
    done
    local fields_str=""
    for f in "${!_fields_seen[@]}"; do
        fields_str+=" ${f}(×${_fields_seen[$f]})"
    done
    info "Champs  :${fields_str}"

    # Tableau récapitulatif
    echo ""
    printf "  ${DIM}%-4s  %-14s  %-6s  %-14s  %-6s${NC}\n" "N°" "CHAMP" "ORDRE" "INSTANT" "LOC"
    printf "  ${DIM}%-4s  %-14s  %-6s  %-14s  %-6s${NC}\n" "──" "─────────────" "─────" "─────────────" "─────"
    for ((i=0; i<_BLOCK_COUNT; i++)); do
        printf "  %-4d  %-14s  %-6s  %-14s  %-6s\n" \
            "$((i+1))" "${_BLOCK_FIELD[$i]}" "${_BLOCK_ORDER[$i]}" \
            "${_BLOCK_INST[$i]}" "${_BLOCK_LOC[$i]}"
    done
    echo ""
}

# ══════════════════════════════════════════
#  MODE INTERACTIF
# ══════════════════════════════════════════

mode_interactif() {
    printf "\n${CYAN}${BOLD}" >/dev/tty
    printf "  ╔══════════════════════════════════════════╗\n" >/dev/tty
    printf "  ║     PARSE RESU — Mode interactif         ║\n" >/dev/tty
    printf "  ║   Navigation  ↑↓  •  espace  •  entrée   ║\n" >/dev/tty
    printf "  ╚══════════════════════════════════════════╝\n" >/dev/tty
    printf "${NC}\n" >/dev/tty

    # ── Sélection du fichier .resu ────────────────────────────────
    section "Fichier .resu"

    local -a resu_files=()
    local f
    while IFS= read -r f; do resu_files+=("$f"); done < <(
        find "${RESU_PATH:-.}" -maxdepth 3 \( -name "*.resu" \) 2>/dev/null \
            | sort -t '/' -k1,1 | head -50
    )

    if [ ${#resu_files[@]} -eq 0 ]; then
        err "Aucun fichier .resu trouvé dans ${RESU_PATH:-.}"
        exit 1
    fi

    if [ ${#resu_files[@]} -eq 1 ]; then
        RESU_FILE="${resu_files[0]}"
        ok "Fichier : $RESU_FILE"
    else
        local -a labels=()
        for f in "${resu_files[@]}"; do
            local sz; sz=$(du -sh "$f" 2>/dev/null | cut -f1 || echo "?")
            labels+=("$(basename "$f")  ${DIM}(${sz})  ${f}${NC}")
        done
        menu_fleches "Fichier .resu à analyser :" "${labels[@]}"
        [ "$_MENU_IDX" -eq -1 ] && { warn "Annulé."; exit 0; }
        RESU_FILE="${resu_files[$_MENU_IDX]}"
    fi

    # ── Scan du fichier ───────────────────────────────────────────
    section "Analyse du fichier"
    info "Lecture de $(basename "$RESU_FILE")..."
    _scan_resu "$RESU_FILE"

    if [ "$_BLOCK_COUNT" -eq 0 ]; then
        err "Aucun bloc de résultats détecté dans $RESU_FILE"
        err "  Le fichier est peut-être vide, corrompu, ou au format IMPR_TABLE"
        err "  (IMPR_TABLE non supporté dans cette version)"
        exit 1
    fi

    _print_summary "$RESU_FILE"

    # ── Sélection des blocs ───────────────────────────────────────
    section "Sélection des blocs"
    local -a bloc_labels=()
    local i
    for ((i=0; i<_BLOCK_COUNT; i++)); do
        bloc_labels+=("$(_block_label $i)")
    done

    menu_cases "Blocs à traiter :" "${bloc_labels[@]}"
    [ ${#_MENU_ITEMS[@]} -eq 0 ] && { warn "Aucun bloc sélectionné. Annulé."; exit 0; }
    local selected_blocs=("${_MENU_ITEMS[@]}")

    # ── Sélection de l'action ─────────────────────────────────────
    section "Action"
    menu_fleches "Que faire avec les blocs sélectionnés ?" \
        "Exporter en CSV" \
        "Afficher les statistiques (min/max/moy)" \
        "Afficher dans le terminal (30 premières lignes)" \
        "Exporter CSV + Statistiques"
    [ "$_MENU_IDX" -eq -1 ] && { warn "Annulé."; exit 0; }
    local action="$_MENU_IDX"

    # ── Dossier de sortie (si CSV) ────────────────────────────────
    local outdir
    outdir="$(dirname "$RESU_FILE")"
    if [ "$action" -eq 0 ] || [ "$action" -eq 3 ]; then
        section "Dossier de sortie"
        saisir "Dossier de sortie pour les CSV" "$outdir"
        outdir="$_SAISIE"
        mkdir -p "$outdir" || { err "Impossible de créer : $outdir"; exit 1; }
        ok "Sortie : $outdir"
    fi

    # ── Exécution ─────────────────────────────────────────────────
    section "Traitement"
    for idx in "${selected_blocs[@]}"; do
        info "[$((idx+1))/$_BLOCK_COUNT] $(_block_label $idx)"
        case "$action" in
            0) _extract_csv "$RESU_FILE" "$idx" "$outdir" "0" >/dev/null ;;
            1) _compute_stats "$RESU_FILE" "$idx" ;;
            2) _display_block "$RESU_FILE" "$idx" 30 ;;
            3) _extract_csv "$RESU_FILE" "$idx" "$outdir" "0" >/dev/null
               _compute_stats "$RESU_FILE" "$idx" ;;
        esac
    done

    ok "Terminé."
}

# ══════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════

RESU_PATH="."
RESU_FILE=""
FILTER_FIELD=""
FILTER_ORDER="0"
DO_CSV=0
DO_STATS=0
DO_ALL=0
OUTDIR=""
QUIET=false
_NARGS=$#

while [ $# -gt 0 ]; do
    case "$1" in
        -f|--field)   FILTER_FIELD="$2";  shift 2 ;;
        -o|--ordre)   FILTER_ORDER="$2";  shift 2 ;;
        -a|--all)     DO_ALL=1;           shift ;;
           --csv)     DO_CSV=1;           shift ;;
           --stats)   DO_STATS=1;         shift ;;
        -O|--outdir)  OUTDIR="$2";        shift 2 ;;
        -q|--quiet)   QUIET=true;         shift ;;
        -h|--help)    usage ;;
        -*)           err "Option inconnue : $1"; usage ;;
        *)
            if [ -f "$1" ]; then
                RESU_FILE="$1"
            elif [ -d "$1" ]; then
                RESU_PATH="$1"
            else
                err "Fichier ou dossier introuvable : $1"; exit 1
            fi
            shift ;;
    esac
done

# Mode interactif : aucun argument, ou dossier sans action explicite
if [ "$_NARGS" -eq 0 ] || { [ -z "$RESU_FILE" ] && [ "$DO_CSV" -eq 0 ] && [ "$DO_STATS" -eq 0 ] && [ "$DO_ALL" -eq 0 ]; }; then
    mode_interactif
    exit 0
fi

# ── Mode CLI ────────────────────────────────────────────────────────────────
set -euo pipefail

# Auto-détection du fichier si dossier fourni
if [ -z "$RESU_FILE" ]; then
    mapfile -t _found < <(find "$RESU_PATH" -maxdepth 3 -name "*.resu" 2>/dev/null | sort)
    if [ ${#_found[@]} -eq 0 ]; then
        err "Aucun .resu dans $RESU_PATH"; exit 1
    fi
    if [ ${#_found[@]} -gt 1 ] && [ -z "$FILTER_FIELD" ] && [ "$DO_ALL" -eq 0 ]; then
        warn "Plusieurs .resu trouvés, utilisation du premier"
    fi
    RESU_FILE="${_found[0]}"
fi

[ -f "$RESU_FILE" ] || { err "Fichier introuvable : $RESU_FILE"; exit 1; }
OUTDIR="${OUTDIR:-$(dirname "$RESU_FILE")}"
mkdir -p "$OUTDIR"

$QUIET || info "Fichier : $RESU_FILE"
$QUIET || info "Analyse en cours..."

_scan_resu "$RESU_FILE"

if [ "$_BLOCK_COUNT" -eq 0 ]; then
    err "Aucun bloc détecté dans $RESU_FILE"; exit 1
fi

$QUIET || _print_summary "$RESU_FILE"

# ── Filtrage ─────────────────────────────────────────────────────────────────
declare -a target_blocs=()
for ((i=0; i<_BLOCK_COUNT; i++)); do
    # Filtre champ
    if [ -n "$FILTER_FIELD" ] && [ "${_BLOCK_FIELD[$i]}" != "$FILTER_FIELD" ]; then
        continue
    fi
    # Filtre ordre
    if [ "$FILTER_ORDER" != "0" ] && [ "${_BLOCK_ORDER[$i]}" != "$FILTER_ORDER" ]; then
        continue
    fi
    target_blocs+=("$i")
done

if [ ${#target_blocs[@]} -eq 0 ]; then
    err "Aucun bloc ne correspond aux filtres (field='${FILTER_FIELD}' ordre='${FILTER_ORDER}')"
    exit 1
fi

$QUIET || info "Blocs ciblés : ${#target_blocs[@]}"

# ── Exécution CLI ─────────────────────────────────────────────────────────────
for idx in "${target_blocs[@]}"; do
    $QUIET || info "Traitement : $(_block_label $idx)"

    if [ "$DO_CSV" -eq 1 ] || [ "$DO_ALL" -eq 1 ]; then
        _extract_csv "$RESU_FILE" "$idx" "$OUTDIR" "$($QUIET && echo 1 || echo 0)"
    fi

    if [ "$DO_STATS" -eq 1 ] || [ "$DO_ALL" -eq 1 ]; then
        _compute_stats "$RESU_FILE" "$idx"
    fi

    # Si aucune action explicite : stats par défaut
    if [ "$DO_CSV" -eq 0 ] && [ "$DO_STATS" -eq 0 ] && [ "$DO_ALL" -eq 0 ]; then
        _compute_stats "$RESU_FILE" "$idx"
    fi
done

$QUIET || ok "Terminé. Sortie : $OUTDIR"

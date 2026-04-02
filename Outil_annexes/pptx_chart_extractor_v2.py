#!/usr/bin/env python3
"""
PPTX Chart Extractor v2.0 — Navigation clavier (flèches ↑↓)
Extraction de graphes PowerPoint via XML brut.
Utilise uniquement zipfile + xml.etree.ElementTree (stdlib) + pandas/matplotlib.

Usage: python pptx_chart_extractor_v2.py [fichier.pptx] [-o dossier_sortie]
Dépendances : pip install pandas matplotlib numpy questionary
"""

import sys
import os
import re
import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np
except ImportError as e:
    print(f"[ERREUR] Dépendance manquante : {e}")
    print("Installe : pip install pandas matplotlib numpy")
    sys.exit(1)

try:
    import questionary
    from questionary import Style as QStyle
except ImportError:
    print("[ERREUR] questionary manquant : pip install questionary")
    sys.exit(1)

# ─── Namespaces XML Office Open ──────────────────────────────────────────────
NS = {
    'c':  'http://schemas.openxmlformats.org/drawingml/2006/chart',
    'a':  'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p':  'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r':  'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel':'http://schemas.openxmlformats.org/package/2006/relationships',
}

CHART_TAGS = {
    'lineChart':     'ligne',
    'line3DChart':   'ligne',
    'barChart':      'barres',
    'bar3DChart':    'barres',
    'scatterChart':  'scatter',
    'bubbleChart':   'scatter',
    'pieChart':      'pie',
    'pie3DChart':    'pie',
    'doughnutChart': 'pie',
    'areaChart':     'aire',
    'area3DChart':   'aire',
    'radarChart':    'radar',
    'stockChart':    'ligne',
    'surfaceChart':  'surface',
    'surface3DChart':'surface',
}

# ─── Style questionary ────────────────────────────────────────────────────────
STYLE = QStyle([
    ("qmark",       "fg:#00d7ff bold"),
    ("question",    "bold"),
    ("answer",      "fg:#00ff87 bold"),
    ("pointer",     "fg:#00d7ff bold"),
    ("highlighted", "fg:#00d7ff bold"),
    ("selected",    "fg:#00ff87"),
    ("separator",   "fg:#555555"),
    ("instruction", "fg:#888888 italic"),
    ("text",        ""),
    ("disabled",    "fg:#555555 italic"),
])

# ─── Couleurs terminal ────────────────────────────────────────────────────────
class C:
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    RESET   = "\033[0m"

def titre(texte):
    largeur = 60
    print(f"\n{C.CYAN}{C.BOLD}{'─' * largeur}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  {texte}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'─' * largeur}{C.RESET}")

def info(t):   print(f"  {C.BLUE}ℹ {C.RESET}{t}")
def ok(t):     print(f"  {C.GREEN}✔ {C.RESET}{t}")
def warn(t):   print(f"  {C.YELLOW}⚠ {C.RESET}{t}")
def erreur(t): print(f"  {C.RED}✘ {C.RESET}{t}")

def slugify(texte):
    texte = re.sub(r'[^\w\s-]', '', str(texte).lower())
    return re.sub(r'[\s-]+', '_', texte).strip('_') or "graphe"

def couleurs(n):
    return cm.tab10(np.linspace(0, 0.9, max(n, 1)))

# ─── Lecture XML bas niveau ───────────────────────────────────────────────────

def lire_pts(ref_el):
    if ref_el is None:
        return {}
    pts = {}
    for pt in ref_el.findall('.//c:pt', NS):
        idx  = pt.get('idx')
        v_el = pt.find('c:v', NS)
        if idx is not None and v_el is not None and v_el.text is not None:
            pts[int(idx)] = v_el.text
    return pts

def lire_ptCount(ref_el):
    pc = ref_el.find('.//c:ptCount', NS) if ref_el is not None else None
    return int(pc.get('val')) if pc is not None else None

def pts_vers_liste(pts_dict, ptCount=None):
    if not pts_dict:
        return []
    n = ptCount if ptCount is not None else max(pts_dict.keys()) + 1
    return [pts_dict.get(i) for i in range(n)]

def lire_ref(parent_el):
    if parent_el is None:
        return [], None
    for ref_tag, type_ref in [('c:strRef', 'str'), ('c:numRef', 'num'), ('c:multiLvlStrRef', 'str')]:
        ref = parent_el.find(ref_tag, NS)
        if ref is not None:
            pts     = lire_pts(ref)
            ptCount = lire_ptCount(ref)
            return pts_vers_liste(pts, ptCount), type_ref
    vals = [v.text for v in parent_el.findall('.//c:v', NS)]
    return vals, 'inline' if vals else None

def lire_nom_serie(ser_el):
    tx = ser_el.find('c:tx', NS)
    if tx is None:
        return None
    v = tx.find('.//c:v', NS)
    if v is not None and v.text:
        return v.text.strip()
    t = tx.find('.//a:t', NS)
    if t is not None and t.text:
        return t.text.strip()
    return None

def lire_titre_chart(chart_tree):
    title_el = chart_tree.find('.//c:title', NS)
    if title_el is None:
        return ""
    v = title_el.find('.//c:v', NS)
    if v is not None and v.text:
        return v.text.strip()
    parties = [t.text for t in title_el.findall('.//a:t', NS) if t.text]
    return "".join(parties).strip()

def lire_titre_slide(slide_tree):
    for sp in slide_tree.findall('.//p:sp', NS):
        ph = sp.find('.//p:ph', NS)
        if ph is not None and ph.get('type') in ('title', 'ctrTitle'):
            parties = [t.text for t in sp.findall('.//a:t', NS) if t.text]
            return "".join(parties).strip()
    return ""

def detecter_famille(chart_tree):
    pa = chart_tree.find('.//c:plotArea', NS)
    if pa is None:
        return 'inconnu', 'inconnu'
    for child in pa:
        local = child.tag.split('}')[-1]
        if local in CHART_TAGS:
            return CHART_TAGS[local], local
    return 'inconnu', 'inconnu'

def to_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return val

# ─── Extraction par type de graphe ───────────────────────────────────────────

def extraire_serie_classique(ser_el):
    nom  = lire_nom_serie(ser_el) or "Série"
    cats, _ = lire_ref(ser_el.find('c:cat', NS))
    vals, _ = lire_ref(ser_el.find('c:val', NS))
    vals = [to_float(v) for v in vals]
    return nom, cats, vals

def extraire_serie_scatter(ser_el):
    nom   = lire_nom_serie(ser_el) or "Série"
    xs, _ = lire_ref(ser_el.find('c:xVal', NS))
    ys, _ = lire_ref(ser_el.find('c:yVal', NS))
    xs = [to_float(v) for v in xs]
    ys = [to_float(v) for v in ys]
    return nom, xs, ys

def construire_df_classique(series_data):
    if not series_data:
        return pd.DataFrame()
    df_dict = {}
    max_len = 0
    for nom, cats, vals in series_data:
        xs = [str(c) if c is not None else "" for c in cats] if cats else [str(i) for i in range(len(vals))]
        max_len = max(max_len, len(xs), len(vals))
        df_dict[f"{nom}_X"] = xs
        df_dict[f"{nom}_Y"] = vals
    for col in df_dict:
        diff = max_len - len(df_dict[col])
        if diff > 0:
            df_dict[col] = df_dict[col] + [None] * diff
    return pd.DataFrame(df_dict)

def construire_df_scatter(series_data):
    if not series_data:
        return pd.DataFrame()
    df_dict = {}
    max_len = 0
    for nom, xs, ys in series_data:
        max_len = max(max_len, len(xs), len(ys))
        df_dict[f"{nom}_X"] = list(xs)
        df_dict[f"{nom}_Y"] = list(ys)
    for col in df_dict:
        diff = max_len - len(df_dict[col])
        if diff > 0:
            df_dict[col] = df_dict[col] + [None] * diff
    return pd.DataFrame(df_dict)

def extraire_chart(chart_tree):
    famille, tag = detecter_famille(chart_tree)
    pa = chart_tree.find('.//c:plotArea', NS)
    if pa is None:
        return pd.DataFrame(), famille, tag
    if famille == 'scatter':
        series_data = [extraire_serie_scatter(s) for s in pa.findall('.//c:ser', NS)]
        return construire_df_scatter(series_data), famille, tag
    series_data = [extraire_serie_classique(s) for s in pa.findall('.//c:ser', NS)]
    return construire_df_classique(series_data), famille, tag

# ─── Analyse du fichier PPTX ─────────────────────────────────────────────────

def charger_rels(zf, rels_path):
    if rels_path not in zf.namelist():
        return {}
    tree = ET.fromstring(zf.read(rels_path))
    return {rel.get('Id'): rel.get('Target') for rel in tree}

def resoudre_chart_path(slide_path, target):
    base     = Path(slide_path).parent
    resolved = (base / target).resolve()
    parts    = resolved.parts
    try:
        idx = parts.index('ppt')
        return '/'.join(parts[idx:])
    except ValueError:
        return str(resolved).lstrip('/')

def analyser_pptx(chemin_pptx):
    graphes    = []
    graphe_idx = 0
    with zipfile.ZipFile(chemin_pptx, 'r') as zf:
        noms   = set(zf.namelist())
        slides = sorted(
            [n for n in noms if re.match(r'ppt/slides/slide\d+\.xml$', n)],
            key=lambda x: int(re.search(r'\d+', x).group())
        )
        for slide_path in slides:
            slide_num   = int(re.search(r'\d+', slide_path).group())
            slide_tree  = ET.fromstring(zf.read(slide_path))
            titre_slide = lire_titre_slide(slide_tree)
            rels_path   = re.sub(
                r'slides/(slide\d+\.xml)$', r'slides/_rels/\1.rels', slide_path
            )
            rels = charger_rels(zf, rels_path)
            for rId, target in rels.items():
                if 'chart' not in target.lower():
                    continue
                chart_path = resoudre_chart_path(slide_path, target)
                if chart_path not in noms:
                    chart_path = 'ppt/charts/' + Path(target).name
                if chart_path not in noms:
                    warn(f"Chart introuvable : {target}")
                    continue
                chart_tree  = ET.fromstring(zf.read(chart_path))
                titre_chart = lire_titre_chart(chart_tree)
                famille, tag = detecter_famille(chart_tree)
                df, _, _    = extraire_chart(chart_tree)
                graphe_idx += 1
                graphes.append({
                    "idx":        graphe_idx,
                    "slide":      slide_num,
                    "titre":      titre_chart or titre_slide or f"Graphe {graphe_idx}",
                    "famille":    famille,
                    "tag_xml":    tag,
                    "df":         df,
                    "chart_path": chart_path,
                })
    return graphes

# ─── Affichage ────────────────────────────────────────────────────────────────

def afficher_resume(graphes):
    titre("GRAPHES TROUVÉS")
    if not graphes:
        warn("Aucun graphe détecté dans ce fichier.")
        return
    print(f"  {'N°':>3}  {'Slide':>5}  {'Type':<10}  {'Lignes':>6}  {'Cols':>4}  Titre")
    print(f"  {'─'*3}  {'─'*5}  {'─'*10}  {'─'*6}  {'─'*4}  {'─'*32}")
    for g in graphes:
        vide  = f" {C.YELLOW}[vide]{C.RESET}" if g["df"].empty else ""
        ncols = len(g["df"].columns) if not g["df"].empty else 0
        print(f"  {C.CYAN}{g['idx']:>3}{C.RESET}  "
              f"  {g['slide']:>3}  "
              f"  {C.BOLD}{g['famille']:<10}{C.RESET}  "
              f"  {len(g['df']):>5}  "
              f"  {ncols:>3}  "
              f"  {g['titre']}{vide}")

def afficher_detail(graphes):
    titre("DÉTAIL D'UN GRAPHE")
    g = _choisir_un_graphe(graphes, "Quel graphe ?")
    if g is None:
        return
    print(f"\n  {C.BOLD}{C.MAGENTA}{g['titre']}{C.RESET}")
    print(f"  Slide      : {g['slide']}")
    print(f"  Balise XML : {g['tag_xml']}")
    print(f"  Famille    : {g['famille']}")
    if not g["df"].empty:
        df = g["df"]
        cols_x      = [c for c in df.columns if str(c).endswith('_X')]
        series_noms = [c[:-2] for c in cols_x]
        print(f"  Lignes     : {len(df)}")
        print(f"  Séries     : {', '.join(series_noms)}")
        print(f"  Colonnes   : {', '.join(str(c) for c in df.columns)}")
        print(f"\n{df.head(10).to_string(index=False)}\n")
    else:
        warn("  Aucune donnée extractible.")

# ─── Sélection de graphes ─────────────────────────────────────────────────────

def _label_graphe(g):
    vide = "  [vide]" if g["df"].empty else ""
    return f"Slide {g['slide']:>2}  {g['famille']:<8}  {g['titre']}{vide}"

def _choisir_un_graphe(graphes, message):
    """Sélectionne un seul graphe via les flèches."""
    choices = [
        questionary.Choice(title=_label_graphe(g), value=g)
        for g in graphes
    ]
    return questionary.select(message, choices=choices, style=STYLE).ask()

def choisir_graphes(graphes, message="Quels graphes ?"):
    """Sélectionne un ou plusieurs graphes (checkbox + option Tous)."""
    choices = [
        questionary.Choice(title=_label_graphe(g), value=g, checked=False)
        for g in graphes
    ]
    # Option raccourci "Tous"
    raccourci = questionary.select(
        message,
        choices=["Sélectionner dans la liste", "── Tous les graphes ──"],
        style=STYLE,
    ).ask()
    if raccourci is None:
        return []
    if raccourci == "── Tous les graphes ──":
        return graphes

    selection = questionary.checkbox(
        "Graphes  (espace pour cocher, entrée pour valider) :",
        choices=choices,
        style=STYLE,
    ).ask()
    return selection if selection else []

# ─── Export CSV ───────────────────────────────────────────────────────────────

def exporter_csv(graphes_selection, dossier_out):
    titre("EXPORT CSV")
    dossier = Path(dossier_out)
    dossier.mkdir(parents=True, exist_ok=True)
    for g in graphes_selection:
        if g["df"].empty:
            warn(f"Graphe {g['idx']} ({g['titre']}) : données vides, ignoré.")
            continue
        nom    = f"graphe_{g['idx']:02d}_{slugify(g['titre'])}.csv"
        chemin = dossier / nom
        g["df"].to_csv(chemin, index=False, encoding="utf-8-sig")
        ok(f"Exporté : {C.BOLD}{chemin}{C.RESET}  "
           f"({len(g['df'])} lignes, {len(g['df'].columns)} colonnes)")

# ─── Plots ────────────────────────────────────────────────────────────────────

def style_ax(ax, titre_graphe, xlabel="", ylabel=""):
    ax.set_title(titre_graphe, fontsize=12, fontweight='bold', pad=10)
    if xlabel: ax.set_xlabel(xlabel, fontsize=9)
    if ylabel: ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, alpha=0.25, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

def plot_graphe(g, sauvegarder=False, dossier_out="."):
    df      = g["df"]
    famille = g["famille"]
    titre_g = g["titre"]
    fig, ax = plt.subplots(figsize=(9, 5))

    if df.empty:
        ax.text(0.5, 0.5, "Données non disponibles", ha='center', va='center',
                transform=ax.transAxes, fontsize=14, color='gray')
        ax.set_title(titre_g, fontsize=12, fontweight='bold')
        plt.tight_layout()
        _finaliser(fig, g, sauvegarder, dossier_out)
        return

    cols_x      = [c for c in df.columns if str(c).endswith('_X')]
    series_noms = [c[:-2] for c in cols_x]
    clrs        = couleurs(max(len(series_noms), 1))

    if famille == 'scatter':
        for i, nom in enumerate(series_noms):
            xs = pd.to_numeric(df[f"{nom}_X"], errors='coerce')
            ys = pd.to_numeric(df[f"{nom}_Y"], errors='coerce')
            ax.scatter(xs, ys, label=nom, color=clrs[i], alpha=0.75, s=45, edgecolors='none')
        style_ax(ax, titre_g, "X", "Y")
        if len(series_noms) > 1:
            ax.legend(fontsize=8)

    elif famille == 'pie':
        if series_noms:
            nom      = series_noms[0]
            labs     = df[f"{nom}_X"].dropna()
            vals_num = pd.to_numeric(df[f"{nom}_Y"], errors='coerce').dropna()
            idx      = vals_num.index
            ax.pie(vals_num,
                   labels=labs.iloc[idx] if len(labs) > max(idx) else labs,
                   autopct='%1.1f%%', startangle=90,
                   colors=couleurs(len(vals_num)), pctdistance=0.82,
                   wedgeprops=dict(linewidth=0.6, edgecolor='white'))
            ax.set_title(titre_g, fontsize=12, fontweight='bold', pad=10)

    elif famille == 'barres':
        x_labels = df[f"{series_noms[0]}_X"].fillna("").tolist() if series_noms else []
        x = np.arange(len(df))
        n = len(series_noms)
        w = 0.8 / max(n, 1)
        for i, nom in enumerate(series_noms):
            offset = (i - n / 2 + 0.5) * w
            vals   = pd.to_numeric(df[f"{nom}_Y"], errors='coerce')
            ax.bar(x + offset, vals, width=w * 0.92, label=nom, color=clrs[i], alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, rotation=30, ha='right', fontsize=8)
        style_ax(ax, titre_g, "", "Valeur")
        if n > 1:
            ax.legend(fontsize=8)

    else:
        x_labels = df[f"{series_noms[0]}_X"].fillna("").tolist() if series_noms else []
        x = np.arange(len(df))
        for i, nom in enumerate(series_noms):
            vals = pd.to_numeric(df[f"{nom}_Y"], errors='coerce')
            if famille == 'aire':
                ax.fill_between(x, vals, alpha=0.35, color=clrs[i])
            ax.plot(x, vals, label=nom, color=clrs[i], linewidth=1.8, marker='o', markersize=3)
        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, rotation=30, ha='right', fontsize=8)
        style_ax(ax, titre_g, "", "Valeur")
        if len(series_noms) > 1:
            ax.legend(fontsize=8)

    plt.tight_layout()
    _finaliser(fig, g, sauvegarder, dossier_out)

def _finaliser(fig, g, sauvegarder, dossier_out):
    if sauvegarder:
        dossier = Path(dossier_out)
        dossier.mkdir(parents=True, exist_ok=True)
        nom    = f"graphe_{g['idx']:02d}_{slugify(g['titre'])}.png"
        chemin = dossier / nom
        fig.savefig(chemin, dpi=150, bbox_inches='tight')
        plt.close(fig)
        ok(f"Image sauvegardée : {C.BOLD}{chemin}{C.RESET}")
    else:
        plt.show()

# ─── Menus actions ────────────────────────────────────────────────────────────

def menu_plot(graphes, dossier_out):
    selection = choisir_graphes(graphes, "Afficher quels graphes ?")
    if not selection:
        return

    mode = questionary.select(
        "Mode d'affichage :",
        choices=[
            "Afficher à l'écran",
            "Sauvegarder en PNG",
            "Les deux",
        ],
        style=STYLE,
    ).ask()
    if mode is None:
        return

    for g in selection:
        info(f"Graphe {g['idx']} : {g['titre']}  ({g['tag_xml']})")
        if g["df"].empty:
            warn("  Données vides — plot ignoré.")
            continue
        if mode == "Afficher à l'écran":
            plot_graphe(g, sauvegarder=False)
        elif mode == "Sauvegarder en PNG":
            plot_graphe(g, sauvegarder=True, dossier_out=dossier_out)
        else:
            plot_graphe(g, sauvegarder=True, dossier_out=dossier_out)
            plot_graphe(g, sauvegarder=False)

def menu_exporter(graphes, dossier_out):
    selection = choisir_graphes(graphes, "Exporter quels graphes en CSV ?")
    if selection:
        exporter_csv(selection, dossier_out)

def menu_tout_exporter(graphes, dossier_out):
    titre("EXPORT COMPLET (CSV + PNG)")
    non_vides = [g for g in graphes if not g["df"].empty]
    if not non_vides:
        warn("Aucun graphe avec des données à exporter.")
        return
    info(f"{len(non_vides)} graphe(s) → {C.BOLD}{dossier_out}/{C.RESET}")
    exporter_csv(non_vides, dossier_out)
    for g in non_vides:
        plot_graphe(g, sauvegarder=True, dossier_out=dossier_out)
    ok(f"Export terminé dans {C.BOLD}{dossier_out}/{C.RESET}")

# ─── Menu principal ───────────────────────────────────────────────────────────

MENU_PRINCIPAL = [
    "Afficher / sauvegarder des graphes",
    "Exporter des graphes en CSV",
    "Export complet (tous CSV + PNG)",
    "Voir le détail d'un graphe",
    "Résumé des graphes",
    "Charger un autre fichier PPTX",
    "Quitter",
]

def charger_pptx(chemin):
    p = Path(chemin)
    if not p.exists():
        erreur(f"Fichier introuvable : {chemin}")
        return None
    if not zipfile.is_zipfile(chemin):
        erreur(f"Fichier invalide (pas un PPTX/ZIP) : {chemin}")
        return None
    info(f"Analyse de {C.BOLD}{p.name}{C.RESET} …")
    graphes = analyser_pptx(chemin)
    ok(f"{len(graphes)} graphe(s) trouvé(s)")
    return graphes

def main():
    parser = argparse.ArgumentParser(
        description="Extracteur de graphes PPTX → CSV + plots  (stdlib XML, navigation flèches)")
    parser.add_argument("fichier", nargs="?", help="Fichier .pptx à analyser")
    parser.add_argument("-o", "--output", default="pptx_export",
                        help="Dossier de sortie (défaut: pptx_export)")
    args = parser.parse_args()

    print(f"\n{C.CYAN}{C.BOLD}")
    print("  ╔══════════════════════════════════════════╗")
    print("  ║      PPTX CHART EXTRACTOR  v2.0          ║")
    print("  ║   Navigation clavier  ↑↓  •  espace      ║")
    print("  ╚══════════════════════════════════════════╝")
    print(C.RESET)

    graphes      = []
    chemin_actif = None
    dossier_out  = args.output

    if args.fichier:
        graphes = charger_pptx(args.fichier)
        if graphes is None:
            sys.exit(1)
        chemin_actif = args.fichier
        afficher_resume(graphes)
    else:
        info("Aucun fichier spécifié.")
        info("Astuce : python pptx_chart_extractor_v2.py presentation.pptx")

    while True:
        titre("MENU PRINCIPAL")
        if chemin_actif:
            info(f"Fichier : {C.BOLD}{Path(chemin_actif).name}{C.RESET}  "
                 f"({len(graphes)} graphe(s))  →  sortie : {C.BOLD}{dossier_out}/{C.RESET}")
        else:
            warn("Aucun fichier chargé")

        choix = questionary.select(
            "Que veux-tu faire ?",
            choices=MENU_PRINCIPAL,
            style=STYLE,
        ).ask()

        if choix is None or choix == "Quitter":
            print(f"\n  {C.GREEN}Au revoir !{C.RESET}\n")
            break

        if choix != "Charger un autre fichier PPTX" and not graphes:
            warn("Charge d'abord un fichier PPTX.")
            continue

        if choix == "Afficher / sauvegarder des graphes":
            menu_plot(graphes, dossier_out)
        elif choix == "Exporter des graphes en CSV":
            menu_exporter(graphes, dossier_out)
        elif choix == "Export complet (tous CSV + PNG)":
            menu_tout_exporter(graphes, dossier_out)
        elif choix == "Voir le détail d'un graphe":
            afficher_detail(graphes)
        elif choix == "Résumé des graphes":
            afficher_resume(graphes)
        elif choix == "Charger un autre fichier PPTX":
            chemin = questionary.text(
                "Chemin du fichier PPTX :", style=STYLE
            ).ask()
            if chemin:
                chemin = chemin.strip('"').strip("'")
                g = charger_pptx(chemin)
                if g is not None:
                    graphes, chemin_actif = g, chemin
                    afficher_resume(graphes)


if __name__ == "__main__":
    main()

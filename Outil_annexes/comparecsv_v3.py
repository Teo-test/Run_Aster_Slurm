#!/usr/bin/env python3
"""
CSV Comparator v3.0 — Navigation clavier (flèches ↑↓)
Usage: python comparecsv_v3.py [fichier1.csv ...] [--sep ,]
Dépendances : pip install pandas matplotlib numpy questionary openpyxl
"""

import sys
import csv
import argparse
from pathlib import Path

# ── Dépendances obligatoires ──────────────────────────────────────────────────
try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np
except ImportError as e:
    print(f"[ERREUR] Dépendance manquante : {e}")
    print("  pip install pandas matplotlib numpy")
    sys.exit(1)

try:
    import questionary
    from questionary import Style as QStyle
except ImportError:
    print("[ERREUR] questionary manquant : pip install questionary")
    sys.exit(1)

# ── Dépendances optionnelles ──────────────────────────────────────────────────
try:
    import openpyxl
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False

# ── Style questionary (thème cyan/vert) ───────────────────────────────────────
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

# ── Couleurs terminal (titres / messages) ──────────────────────────────────────
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

# ── Séparateurs disponibles ───────────────────────────────────────────────────
SEPARATEURS = {
    "Auto-détection":    None,
    "Virgule      ( , )": ",",
    "Point-virgule ( ; )": ";",
    "Tabulation   ( \\t )": "\t",
    "Pipe         ( | )": "|",
    "Espace       (   )": " ",
}

SEP_EXPORT = {
    "Virgule      ( , )": ",",
    "Point-virgule ( ; )": ";",
    "Tabulation   ( \\t )": "\t",
    "Pipe         ( | )": "|",
}

def choisir_separateur(titre_q="Séparateur :", avec_auto=True):
    """Sélectionne un séparateur via les flèches."""
    choices = list(SEPARATEURS.keys()) if avec_auto else list(SEP_EXPORT.keys())
    choix = questionary.select(titre_q, choices=choices, style=STYLE).ask()
    if choix is None:
        return ","
    return (SEPARATEURS if avec_auto else SEP_EXPORT).get(choix, ",")

# ── Chargement CSV ────────────────────────────────────────────────────────────
def charger_csv(chemin, sep=None):
    """Charge un CSV avec détection auto ou séparateur fourni."""
    try:
        if sep is None:
            with open(chemin, "r", encoding="utf-8-sig") as f:
                echantillon = f.read(4096)
                dialect = csv.Sniffer().sniff(echantillon, delimiters=",;|\t ")
                sep = dialect.delimiter
        df = pd.read_csv(chemin, sep=sep, encoding="utf-8-sig")
        return df, sep
    except Exception as e:
        erreur(f"Impossible de charger {chemin} : {e}")
        return None, None

def charger_fichiers(chemins, sep=None):
    datasets = {}
    for chemin in chemins:
        p = Path(chemin)
        if not p.exists():
            warn(f"Fichier introuvable : {chemin}")
            continue
        df, sep_utilise = charger_csv(chemin, sep)
        if df is not None:
            datasets[p.stem] = {"df": df, "chemin": chemin, "sep": sep_utilise}
            ok(f"Chargé : {C.BOLD}{p.name}{C.RESET}  "
               f"({len(df)} lignes, {len(df.columns)} colonnes, sep='{sep_utilise}')")
    return datasets

def ajouter_fichier(datasets):
    chemin = questionary.text("Chemin du fichier CSV :", style=STYLE).ask()
    if not chemin:
        return
    chemin = chemin.strip('"').strip("'")
    p = Path(chemin)
    if not p.exists():
        erreur(f"Fichier introuvable : {chemin}")
        return
    sep = choisir_separateur("Séparateur du fichier :", avec_auto=True)
    df, sep_utilise = charger_csv(chemin, sep)
    if df is not None:
        datasets[p.stem] = {"df": df, "chemin": chemin, "sep": sep_utilise}
        ok(f"Ajouté : {C.BOLD}{p.name}{C.RESET}  (sep='{sep_utilise}')")

# ── Aperçu ────────────────────────────────────────────────────────────────────
def afficher_apercu(datasets):
    titre("APERÇU DES DONNÉES")
    for nom, d in datasets.items():
        df = d["df"]
        print(f"\n  {C.BOLD}{C.MAGENTA}{nom}{C.RESET}  →  {d['chemin']}")
        print(f"  {C.DIM}Lignes: {len(df)}  |  Colonnes: {len(df.columns)}{C.RESET}")
        cols_num = df.select_dtypes(include="number").columns.tolist()
        cols_cat = df.select_dtypes(exclude="number").columns.tolist()
        if cols_num:
            print(f"  {C.GREEN}Numériques:{C.RESET} {', '.join(cols_num)}")
        if cols_cat:
            print(f"  {C.YELLOW}Texte/Date:{C.RESET} {', '.join(cols_cat)}")
        print(f"\n{df.head(3).to_string(index=False)}\n")

def afficher_stats(datasets):
    titre("STATISTIQUES DESCRIPTIVES")
    noms = list(datasets.keys())
    choix = questionary.select(
        "Quel dataset ?",
        choices=noms + ["── Tous ──"],
        style=STYLE,
    ).ask()
    if choix is None:
        return
    selection = noms if choix == "── Tous ──" else [choix]
    for nom in selection:
        df = datasets[nom]["df"]
        print(f"\n  {C.BOLD}{C.MAGENTA}── {nom} ──{C.RESET}")
        print(df.describe().to_string())

# ── Mini-barre ASCII (sans codes ANSI pour questionary) ───────────────────────
def _mini_barre(valeurs, largeur=12):
    """Résumé visuel d'une colonne, sans codes ANSI."""
    try:
        nums = pd.to_numeric(valeurs, errors="coerce").dropna()
        if len(nums) == 0:
            raise ValueError
        vmin, vmax = nums.min(), nums.max()
        etendue = vmax - vmin if vmax != vmin else 1
        moy = nums.mean()
        remplissage = int((moy - vmin) / etendue * largeur)
        barre = "█" * remplissage + "░" * (largeur - remplissage)
        return f"[{barre}] min={vmin:.3g} moy={moy:.3g} max={vmax:.3g} n={len(nums)}"
    except Exception:
        pass
    uniques = valeurs.dropna().astype(str).unique()
    n = len(uniques)
    apercu = ", ".join(uniques[:4])
    if n > 4:
        apercu += f", … ({n} uniques)"
    return f"[{apercu}]"

# ── Sélection colonnes ────────────────────────────────────────────────────────
def choisir_colonne(df, message, filtre_num=False):
    if filtre_num:
        cols = df.select_dtypes(include="number").columns.tolist()
        if not cols:
            erreur("Aucune colonne numérique disponible.")
            return None
    else:
        cols = df.columns.tolist()

    largeur = max(len(c) for c in cols) + 2
    choices = [
        questionary.Choice(title=f"{col:<{largeur}} {_mini_barre(df[col])}", value=col)
        for col in cols
    ]
    return questionary.select(message, choices=choices, style=STYLE).ask()

def choisir_colonne_multi(df, message, filtre_num=False):
    if filtre_num:
        cols = df.select_dtypes(include="number").columns.tolist()
        if not cols:
            erreur("Aucune colonne numérique disponible.")
            return []
    else:
        cols = df.columns.tolist()

    largeur = max(len(c) for c in cols) + 2
    choices = [
        questionary.Choice(title=f"{col:<{largeur}} {_mini_barre(df[col])}", value=col)
        for col in cols
    ]
    result = questionary.checkbox(
        message + "  (espace pour sélectionner, entrée pour valider)",
        choices=choices,
        style=STYLE,
    ).ask()
    return result if result is not None else []

def choisir_datasets(datasets, allow_multiple=True):
    noms = list(datasets.keys())
    if len(noms) == 1:
        return noms
    if allow_multiple:
        result = questionary.checkbox(
            "Quels fichiers ?  (espace pour sélectionner, entrée pour valider)",
            choices=[questionary.Choice(title=n, value=n) for n in noms],
            style=STYLE,
        ).ask()
        return result if result else noms
    choix = questionary.select("Quel fichier ?", choices=noms, style=STYLE).ask()
    return [choix] if choix else []

# ── Personnalisation titres / axes ────────────────────────────────────────────
def demander_titres(titre_defaut="", xlabel_defaut="", ylabel_defaut=""):
    """Demande interactivement le titre du graphe et les labels des axes."""
    t = questionary.text(
        "Titre du graphe :", default=titre_defaut, style=STYLE
    ).ask()
    x = questionary.text(
        "Label axe X :", default=xlabel_defaut, style=STYLE
    ).ask()
    y = questionary.text(
        "Label axe Y :", default=ylabel_defaut, style=STYLE
    ).ask()
    return (t or titre_defaut), (x or xlabel_defaut), (y or ylabel_defaut)

# ── Style graphe commun ───────────────────────────────────────────────────────
TYPES_GRAPHE = {
    "Ligne (X vs Y)":            "ligne",
    "Nuage de points (scatter)":  "scatter",
    "Barres":                    "barres",
    "Histogramme":               "histo",
    "Boîte à moustaches":        "boxplot",
    "Aire empilée":              "aire",
    "Corrélation (heatmap)":     "heatmap",
}

def appliquer_style(ax, titre_graphe, xlabel="", ylabel=""):
    ax.set_title(titre_graphe, fontsize=13, fontweight="bold", pad=12)
    if xlabel: ax.set_xlabel(xlabel, fontsize=10)
    if ylabel: ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

def couleurs_datasets(n):
    return cm.tab10(np.linspace(0, 0.9, max(n, 1)))

# ── Graphe ligne ──────────────────────────────────────────────────────────────
def graphe_ligne(datasets, selection):
    series = []
    for nom in selection:
        df = datasets[nom]["df"]
        cols_y = choisir_colonne_multi(df, f"[{nom}] Colonnes Y", filtre_num=True)
        for col_y in cols_y:
            series.append((nom, col_y))
    if not series:
        return

    titre("CHOIX DE L'AXE X PAR SÉRIE")
    series_configs = []
    for nom, col_y in series:
        df = datasets[nom]["df"]
        info(f"Série  {C.BOLD}{C.MAGENTA}{nom}{C.RESET} — {C.BOLD}{col_y}{C.RESET}")
        col_x = choisir_colonne(df, f"Colonne X pour '{col_y}'")
        if col_x:
            series_configs.append((nom, col_x, col_y))
    if not series_configs:
        return

    x_def = ", ".join(dict.fromkeys(c[1] for c in series_configs))
    titre_g, xlabel, ylabel = demander_titres("Graphe Ligne", x_def, "Valeur")

    fig, ax = plt.subplots(figsize=(10, 5))
    clrs = couleurs_datasets(len(series_configs))
    for i, (nom, col_x, col_y) in enumerate(series_configs):
        df = datasets[nom]["df"]
        label = f"{nom} — {col_y}" if len(selection) > 1 else col_y
        ax.plot(df[col_x], df[col_y], label=label, color=clrs[i],
                linewidth=1.8, marker="o", markersize=3)
    appliquer_style(ax, titre_g, xlabel, ylabel)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.show()

# ── Scatter ───────────────────────────────────────────────────────────────────
def graphe_scatter(datasets, selection):
    series = []
    for nom in selection:
        df = datasets[nom]["df"]
        cols_y = choisir_colonne_multi(df, f"[{nom}] Colonnes Y (numériques)", filtre_num=True)
        for col_y in cols_y:
            series.append((nom, col_y))
    if not series:
        return

    titre("CHOIX DE L'AXE X PAR SÉRIE")
    series_configs = []
    for nom, col_y in series:
        df = datasets[nom]["df"]
        info(f"Série  {C.BOLD}{C.MAGENTA}{nom}{C.RESET} — {C.BOLD}{col_y}{C.RESET}")
        col_x = choisir_colonne(df, f"Colonne X pour '{col_y}'", filtre_num=True)
        if col_x:
            series_configs.append((nom, col_x, col_y))
    if not series_configs:
        return

    x_def = ", ".join(dict.fromkeys(c[1] for c in series_configs))
    titre_g, xlabel, ylabel = demander_titres("Nuage de points", x_def, "Y")

    fig, ax = plt.subplots(figsize=(8, 6))
    clrs = couleurs_datasets(len(series_configs))
    for i, (nom, col_x, col_y) in enumerate(series_configs):
        df = datasets[nom]["df"]
        label = f"{nom} — {col_y}" if len(selection) > 1 else col_y
        ax.scatter(df[col_x], df[col_y], label=label, color=clrs[i],
                   alpha=0.65, s=30, edgecolors="none")
    appliquer_style(ax, titre_g, xlabel, ylabel)
    if len(series_configs) > 1:
        ax.legend(fontsize=8)
    plt.tight_layout()
    plt.show()

# ── Barres ────────────────────────────────────────────────────────────────────
def graphe_barres(datasets, selection):
    series = []
    for nom in selection:
        df = datasets[nom]["df"]
        cols_y = choisir_colonne_multi(df, f"[{nom}] Colonnes Y (valeurs)", filtre_num=True)
        for col_y in cols_y:
            series.append((nom, col_y))
    if not series:
        return

    titre("CHOIX DE L'AXE X PAR SÉRIE")
    series_configs = []
    for nom, col_y in series:
        df = datasets[nom]["df"]
        info(f"Série  {C.BOLD}{C.MAGENTA}{nom}{C.RESET} — {C.BOLD}{col_y}{C.RESET}")
        col_x = choisir_colonne(df, f"Colonne catégories X pour '{col_y}'")
        if col_x:
            series_configs.append((nom, col_x, col_y))
    if not series_configs:
        return

    x_def = ", ".join(dict.fromkeys(c[1] for c in series_configs))
    titre_g, xlabel, ylabel = demander_titres("Graphe Barres", x_def, "Valeur")

    fig, ax = plt.subplots(figsize=(10, 5))
    n = len(series_configs)
    clrs = couleurs_datasets(n)
    width = 0.8 / max(n, 1)

    for i, (nom, col_x, col_y) in enumerate(series_configs):
        df = datasets[nom]["df"]
        grouped = df.groupby(col_x)[col_y].mean().reset_index()
        x = np.arange(len(grouped))
        offset = (i - n / 2 + 0.5) * width
        label = f"{nom} — {col_y}" if len(selection) > 1 else col_y
        ax.bar(x + offset, grouped[col_y], width=width * 0.9,
               label=label, color=clrs[i], alpha=0.85)
        if i == 0:
            ax.set_xticks(x)
            ax.set_xticklabels(grouped[col_x], rotation=45, ha="right", fontsize=8)

    appliquer_style(ax, titre_g, xlabel, ylabel)
    if n > 1:
        ax.legend(fontsize=8)
    plt.tight_layout()
    plt.show()

# ── Histogramme ───────────────────────────────────────────────────────────────
def graphe_histo(datasets, selection):
    df_ref = datasets[selection[0]]["df"]
    col = choisir_colonne(df_ref, "Colonne à distribuer", filtre_num=True)
    if col is None:
        return
    bins_str = questionary.text("Nombre de bins :", default="20", style=STYLE).ask() or "20"
    try:
        bins = int(bins_str)
    except ValueError:
        bins = 20

    titre_g, xlabel, ylabel = demander_titres(f"Distribution : {col}", col, "Fréquence")

    fig, ax = plt.subplots(figsize=(9, 5))
    clrs = couleurs_datasets(len(selection))
    for i, nom in enumerate(selection):
        df = datasets[nom]["df"]
        if col not in df.columns:
            continue
        ax.hist(df[col].dropna(), bins=bins, label=nom, color=clrs[i],
                alpha=0.6, edgecolor="white", linewidth=0.5)
    appliquer_style(ax, titre_g, xlabel, ylabel)
    if len(selection) > 1:
        ax.legend(fontsize=8)
    plt.tight_layout()
    plt.show()

# ── Boxplot ───────────────────────────────────────────────────────────────────
def graphe_boxplot(datasets, selection):
    df_ref = datasets[selection[0]]["df"]
    cols = choisir_colonne_multi(df_ref, "Colonnes à comparer", filtre_num=True)
    if not cols:
        return

    titre_g, _, ylabel = demander_titres("Boîtes à moustaches", "", "Valeur")

    fig, axes = plt.subplots(1, len(cols), figsize=(4 * len(cols), 5), squeeze=False)
    clrs = couleurs_datasets(len(selection))

    for j, col in enumerate(cols):
        ax = axes[0][j]
        data, labels = [], []
        for i, nom in enumerate(selection):
            df = datasets[nom]["df"]
            if col in df.columns:
                data.append(df[col].dropna().values)
                labels.append(nom)
        bp = ax.boxplot(data, labels=labels, patch_artist=True,
                        medianprops=dict(color="black", linewidth=2))
        for patch, c in zip(bp["boxes"], clrs):
            patch.set_facecolor(c)
            patch.set_alpha(0.7)
        ax.set_title(col, fontweight="bold")
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="x", rotation=20)
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=10)

    fig.suptitle(titre_g, fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.show()

# ── Aire empilée ──────────────────────────────────────────────────────────────
def graphe_aire(datasets, selection):
    nom = selection[0]
    if len(selection) > 1:
        info("Aire empilée fonctionne sur un seul dataset — utilisation du premier.")
    df = datasets[nom]["df"]

    col_x  = choisir_colonne(df, "Colonne X (abscisse)")
    cols_y = choisir_colonne_multi(df, "Colonnes Y à empiler", filtre_num=True)
    if not cols_y:
        return

    titre_g, xlabel, ylabel = demander_titres(
        f"Aire empilée — {nom}", col_x or "", "Valeur cumulée"
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    clrs = couleurs_datasets(len(cols_y))
    ax.stackplot(df[col_x], [df[c] for c in cols_y if c in df.columns],
                 labels=cols_y, colors=clrs, alpha=0.8)
    appliquer_style(ax, titre_g, xlabel, ylabel)
    ax.legend(fontsize=8, loc="upper left")
    plt.tight_layout()
    plt.show()

# ── Heatmap corrélation ───────────────────────────────────────────────────────
def graphe_heatmap(datasets, selection):
    nom = selection[0]
    if len(selection) > 1:
        info("Heatmap sur un seul dataset — utilisation du premier.")
    df = datasets[nom]["df"]
    cols_num = df.select_dtypes(include="number").columns.tolist()
    if len(cols_num) < 2:
        erreur("Pas assez de colonnes numériques pour une heatmap.")
        return

    titre_g, _, _ = demander_titres(f"Matrice de corrélation — {nom}")

    corr = df[cols_num].corr()
    fig, ax = plt.subplots(figsize=(max(6, len(cols_num)), max(5, len(cols_num) - 1)))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax, label="Corrélation")
    ax.set_xticks(range(len(cols_num)))
    ax.set_yticks(range(len(cols_num)))
    ax.set_xticklabels(cols_num, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(cols_num, fontsize=8)
    for i in range(len(cols_num)):
        for j in range(len(cols_num)):
            val = corr.iloc[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(val) > 0.5 else "black")
    ax.set_title(titre_g, fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()
    plt.show()

# ── Routeur graphes ───────────────────────────────────────────────────────────
def menu_graphe(datasets):
    if not datasets:
        erreur("Aucun fichier chargé !")
        return

    titre("TRACER UN GRAPHE")
    selection = choisir_datasets(datasets)
    if not selection:
        return

    type_label = questionary.select(
        "Type de graphe :",
        choices=list(TYPES_GRAPHE.keys()),
        style=STYLE,
    ).ask()
    if type_label is None:
        return

    dispatch = {
        "ligne":   graphe_ligne,
        "scatter": graphe_scatter,
        "barres":  graphe_barres,
        "histo":   graphe_histo,
        "boxplot": graphe_boxplot,
        "aire":    graphe_aire,
        "heatmap": graphe_heatmap,
    }
    dispatch[TYPES_GRAPHE[type_label]](datasets, selection)

# ── Export ─────────────────────────────────────────────────────────────────────
def _formats_export():
    fmts = ["CSV", "TSV (tabulation)", "TXT (espace)", "JSON", "Parquet"]
    if EXCEL_OK:
        fmts.insert(4, "Excel (.xlsx)")
    return fmts

def exporter_merge(datasets):
    titre("EXPORTER / FUSIONNER")
    selection = choisir_datasets(datasets)
    if not selection:
        return

    dfs = [datasets[n]["df"].assign(_source=n) for n in selection]
    merged = pd.concat(dfs, ignore_index=True)

    # ── Sélection des colonnes à exporter ─────────────────────────────────────
    toutes_cols = merged.columns.tolist()
    largeur_col = max(len(c) for c in toutes_cols) + 2
    choices_cols = [
        questionary.Choice(
            title=f"{col:<{largeur_col}} {_mini_barre(merged[col])}",
            value=col,
            checked=True,  # toutes cochées par défaut
        )
        for col in toutes_cols
    ]
    cols_export = questionary.checkbox(
        "Colonnes à exporter  (espace pour décocher, entrée pour valider) :",
        choices=choices_cols,
        style=STYLE,
    ).ask()
    if not cols_export:
        warn("Aucune colonne sélectionnée, export annulé.")
        return
    merged = merged[cols_export]

    fmt = questionary.select(
        "Format d'export :",
        choices=_formats_export(),
        style=STYLE,
    ).ask()
    if fmt is None:
        return

    ext_defaut = {
        "CSV":             ".csv",
        "TSV (tabulation)": ".tsv",
        "TXT (espace)":    ".txt",
        "JSON":            ".json",
        "Excel (.xlsx)":   ".xlsx",
        "Parquet":         ".parquet",
    }
    chemin_out = questionary.text(
        "Nom du fichier de sortie :",
        default=f"export_merge{ext_defaut.get(fmt, '.csv')}",
        style=STYLE,
    ).ask()
    if not chemin_out:
        return

    try:
        if fmt == "CSV":
            sep = choisir_separateur("Séparateur CSV :", avec_auto=False)
            merged.to_csv(chemin_out, index=False, sep=sep, encoding="utf-8-sig")

        elif fmt == "TSV (tabulation)":
            merged.to_csv(chemin_out, index=False, sep="\t", encoding="utf-8-sig")

        elif fmt == "TXT (espace)":
            merged.to_csv(chemin_out, index=False, sep=" ", encoding="utf-8-sig")

        elif fmt == "JSON":
            orient_label = questionary.select(
                "Format JSON :",
                choices=[
                    "records  — liste d'objets  [ {col: val, …}, … ]",
                    "table    — avec schéma de types",
                    "index    — dictionnaire indexé",
                ],
                style=STYLE,
            ).ask()
            orient_map = {
                "records  — liste d'objets  [ {col: val, …}, … ]": "records",
                "table    — avec schéma de types":                  "table",
                "index    — dictionnaire indexé":                   "index",
            }
            merged.to_json(
                chemin_out,
                orient=orient_map.get(orient_label, "records"),
                force_ascii=False,
                indent=2,
            )

        elif fmt == "Excel (.xlsx)":
            sheet = (
                questionary.text("Nom de la feuille :", default="Données", style=STYLE).ask()
                or "Données"
            )
            merged.to_excel(chemin_out, index=False, sheet_name=sheet)

        elif fmt == "Parquet":
            merged.to_parquet(chemin_out, index=False)

        ok(f"Exporté : {chemin_out}  ({len(merged)} lignes, {len(merged.columns)} colonnes)")

    except Exception as e:
        erreur(f"Erreur lors de l'export : {e}")

# ── Séparation par groupes de colonnes ───────────────────────────────────────
def diviser_par_groupes(datasets):
    """
    Détecte les groupes de lignes partageant le même ensemble de colonnes
    non-nulles et les enregistre comme datasets distincts.

    Utile pour les CSV où plusieurs séries de mesures sont empilées dans le
    même fichier avec des colonnes différentes remplies selon les lignes.
    """
    titre("DIVISER PAR GROUPES DE COLONNES")
    noms = list(datasets.keys())
    nom = questionary.select("Quel dataset à diviser ?", choices=noms, style=STYLE).ask()
    if nom is None:
        return

    df = datasets[nom]["df"]

    # Calcule la "signature" de chaque ligne : frozenset des colonnes non-NaN
    signatures = df.apply(
        lambda row: frozenset(df.columns[row.notna()].tolist()), axis=1
    )
    groupes = signatures.unique()

    if len(groupes) == 1:
        warn("Toutes les lignes ont le même ensemble de colonnes — rien à diviser.")
        return

    info(f"{len(groupes)} groupe(s) détecté(s) :")
    groupes_tries = sorted(groupes, key=lambda g: -signatures.value_counts()[g])
    for i, g in enumerate(groupes_tries):
        n_lignes = (signatures == g).sum()
        cols = ", ".join(sorted(g))
        print(f"    {C.CYAN}{i+1}{C.RESET}. ({n_lignes} lignes)  {C.DIM}{cols}{C.RESET}")

    print()
    confirmer = questionary.confirm(
        f"Créer {len(groupes_tries)} sous-datasets à partir de « {nom} » ?",
        default=True,
        style=STYLE,
    ).ask()
    if not confirmer:
        return

    for i, sig in enumerate(groupes_tries):
        masque = signatures == sig
        sous_df = df[masque][sorted(sig)].reset_index(drop=True)

        # Nom par défaut : nom_base + colonnes du groupe
        cols_courtes = "_".join(c[:6] for c in sorted(sig))
        sous_nom_defaut = f"{nom}_g{i+1}_{cols_courtes}"[:40]
        sous_nom = questionary.text(
            f"Nom du sous-dataset {i+1}/{len(groupes_tries)} :",
            default=sous_nom_defaut,
            style=STYLE,
        ).ask()
        if not sous_nom:
            sous_nom = sous_nom_defaut

        datasets[sous_nom] = {
            "df": sous_df,
            "chemin": f"(issu de {datasets[nom]['chemin']})",
            "sep": datasets[nom]["sep"],
        }
        ok(f"Créé : {C.BOLD}{sous_nom}{C.RESET}  ({len(sous_df)} lignes, colonnes : {', '.join(sorted(sig))})")

# ── Menu principal ─────────────────────────────────────────────────────────────
MENU_PRINCIPAL = [
    "Tracer un graphe",
    "Aperçu des données",
    "Statistiques descriptives",
    "Ajouter un fichier CSV",
    "Diviser par groupes de colonnes",
    "Exporter / Fusionner",
    "Quitter",
]

def main():
    parser = argparse.ArgumentParser(description="Comparateur interactif de fichiers CSV v3")
    parser.add_argument("fichiers", nargs="*", help="Fichiers CSV à charger au démarrage")
    parser.add_argument(
        "--sep",
        help="Séparateur forcé au chargement (ex: , ; \\t |)",
        default=None,
    )
    args = parser.parse_args()

    print(f"\n{C.CYAN}{C.BOLD}")
    print("  ╔══════════════════════════════════════════╗")
    print("  ║        CSV COMPARATOR  v3.0              ║")
    print("  ║   Navigation clavier  ↑↓  •  espace      ║")
    print("  ╚══════════════════════════════════════════╝")
    print(C.RESET)

    datasets = {}

    if args.fichiers:
        titre("CHARGEMENT DES FICHIERS")
        sep = args.sep.replace("\\t", "\t") if args.sep else None
        datasets = charger_fichiers(args.fichiers, sep=sep)
    else:
        info("Aucun fichier spécifié. Utilise le menu pour en ajouter.")
        info("Astuce : python comparecsv_v3.py fichier1.csv fichier2.csv")

    while True:
        titre("MENU PRINCIPAL")
        if datasets:
            info(f"Fichiers chargés : {C.BOLD}{', '.join(datasets.keys())}{C.RESET}")
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
        elif choix == "Tracer un graphe":
            menu_graphe(datasets)
        elif choix == "Aperçu des données":
            afficher_apercu(datasets) if datasets else warn("Aucun fichier chargé.")
        elif choix == "Statistiques descriptives":
            afficher_stats(datasets) if datasets else warn("Aucun fichier chargé.")
        elif choix == "Ajouter un fichier CSV":
            ajouter_fichier(datasets)
        elif choix == "Diviser par groupes de colonnes":
            diviser_par_groupes(datasets) if datasets else warn("Aucun fichier chargé.")
        elif choix == "Exporter / Fusionner":
            exporter_merge(datasets) if datasets else warn("Aucun fichier chargé.")


if __name__ == "__main__":
    main()

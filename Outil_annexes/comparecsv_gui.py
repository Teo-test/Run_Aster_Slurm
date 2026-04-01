#!/usr/bin/env python3
"""
CSV Comparator GUI — Interface graphique avec drag & drop
Usage: python comparecsv_gui.py [fichier1.csv fichier2.csv ...]

Dépendance supplémentaire : pip install tkinterdnd2
"""

import sys
import csv
import re
import argparse
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    import tkinterdnd2 as dnd
except ImportError as e:
    print(f"[ERREUR] {e}")
    print("Installe : pip install tkinterdnd2")
    sys.exit(1)

try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
except ImportError as e:
    print(f"[ERREUR] {e}")
    print("Installe : pip install pandas matplotlib numpy")
    sys.exit(1)


# ─── Fonctions de traitement (adaptées de comparecsv.py) ────────────────────

def charger_csv(chemin, sep=None):
    """Charge un CSV avec détection automatique du séparateur."""
    try:
        if sep is None:
            with open(chemin, 'r', encoding='utf-8-sig') as f:
                echantillon = f.read(4096)
                dialect = csv.Sniffer().sniff(echantillon, delimiters=',;|\t')
                sep = dialect.delimiter
        df = pd.read_csv(chemin, sep=sep, encoding='utf-8-sig')
        return df, sep
    except Exception as e:
        raise RuntimeError(f"Impossible de charger {Path(chemin).name} : {e}")


def couleurs_datasets(n):
    return cm.tab10(np.linspace(0, 0.9, max(n, 1)))


def appliquer_style(ax, titre_graphe, xlabel="", ylabel=""):
    ax.set_title(titre_graphe, fontsize=13, fontweight='bold', pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


def build_fig_ligne(datasets, selection, col_x, cols_y):
    fig, ax = plt.subplots(figsize=(9, 5))
    pairs = [(nom, cy) for nom in selection for cy in cols_y]
    clrs = couleurs_datasets(len(pairs))
    for i, (nom, col_y) in enumerate(pairs):
        df = datasets[nom]["df"]
        if col_x not in df.columns or col_y not in df.columns:
            continue
        label = f"{nom} — {col_y}" if len(pairs) > 1 else col_y
        ax.plot(df[col_x], df[col_y], label=label, color=clrs[i],
                linewidth=1.8, marker='o', markersize=3)
    appliquer_style(ax, "Graphe Ligne", col_x, "Valeur")
    if len(pairs) > 1:
        ax.legend(fontsize=8)
    plt.tight_layout()
    return fig


def build_fig_scatter(datasets, selection, col_x, cols_y):
    fig, ax = plt.subplots(figsize=(8, 6))
    pairs = [(nom, cy) for nom in selection for cy in cols_y]
    clrs = couleurs_datasets(len(pairs))
    for i, (nom, col_y) in enumerate(pairs):
        df = datasets[nom]["df"]
        if col_x not in df.columns or col_y not in df.columns:
            continue
        label = f"{nom} — {col_y}" if len(pairs) > 1 else col_y
        ax.scatter(df[col_x], df[col_y], label=label, color=clrs[i],
                   alpha=0.65, s=30, edgecolors='none')
    appliquer_style(ax, "Nuage de points", col_x, "Y")
    if len(pairs) > 1:
        ax.legend(fontsize=8)
    plt.tight_layout()
    return fig


def build_fig_barres(datasets, selection, col_x, cols_y):
    fig, ax = plt.subplots(figsize=(10, 5))
    pairs = [(nom, cy) for nom in selection for cy in cols_y]
    n = len(pairs)
    clrs = couleurs_datasets(n)
    w = 0.8 / max(n, 1)
    for i, (nom, col_y) in enumerate(pairs):
        df = datasets[nom]["df"]
        if col_x not in df.columns or col_y not in df.columns:
            continue
        grouped = df.groupby(col_x)[col_y].mean().reset_index()
        x = np.arange(len(grouped))
        offset = (i - n / 2 + 0.5) * w
        label = f"{nom} — {col_y}" if n > 1 else col_y
        ax.bar(x + offset, grouped[col_y], width=w * 0.9,
               label=label, color=clrs[i], alpha=0.85)
        if i == 0:
            ax.set_xticks(x)
            ax.set_xticklabels(grouped[col_x], rotation=45, ha='right', fontsize=8)
    appliquer_style(ax, "Graphe Barres", col_x, "Valeur")
    if n > 1:
        ax.legend(fontsize=8)
    plt.tight_layout()
    return fig


def build_fig_histo(datasets, selection, col, bins):
    fig, ax = plt.subplots(figsize=(9, 5))
    clrs = couleurs_datasets(len(selection))
    for i, nom in enumerate(selection):
        df = datasets[nom]["df"]
        if col not in df.columns:
            continue
        ax.hist(df[col].dropna(), bins=bins, label=nom, color=clrs[i],
                alpha=0.6, edgecolor='white', linewidth=0.5)
    appliquer_style(ax, f"Distribution : {col}", col, "Fréquence")
    if len(selection) > 1:
        ax.legend(fontsize=8)
    plt.tight_layout()
    return fig


def build_fig_boxplot(datasets, selection, cols_y):
    fig, axes = plt.subplots(1, len(cols_y), figsize=(4 * len(cols_y), 5), squeeze=False)
    clrs = couleurs_datasets(len(selection))
    for j, col in enumerate(cols_y):
        ax = axes[0][j]
        data, labels = [], []
        for i, nom in enumerate(selection):
            df = datasets[nom]["df"]
            if col in df.columns:
                data.append(df[col].dropna().values)
                labels.append(nom)
        bp = ax.boxplot(data, labels=labels, patch_artist=True,
                        medianprops=dict(color='black', linewidth=2))
        for patch, c in zip(bp['boxes'], clrs):
            patch.set_facecolor(c)
            patch.set_alpha(0.7)
        ax.set_title(col, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(axis='x', rotation=20)
    fig.suptitle("Boîtes à moustaches", fontsize=13, fontweight='bold')
    plt.tight_layout()
    return fig


def build_fig_aire(datasets, selection, col_x, cols_y):
    nom = selection[0]
    df = datasets[nom]["df"]
    fig, ax = plt.subplots(figsize=(10, 5))
    valid_y = [c for c in cols_y if c in df.columns]
    clrs = couleurs_datasets(len(valid_y))
    ax.stackplot(df[col_x], [df[c] for c in valid_y],
                 labels=valid_y, colors=clrs, alpha=0.8)
    appliquer_style(ax, f"Aire empilée — {nom}", col_x, "Valeur cumulée")
    ax.legend(fontsize=8, loc='upper left')
    plt.tight_layout()
    return fig


def build_fig_heatmap(datasets, selection):
    nom = selection[0]
    df = datasets[nom]["df"]
    cols_num = df.select_dtypes(include='number').columns.tolist()
    if len(cols_num) < 2:
        raise ValueError("Pas assez de colonnes numériques pour une heatmap.")
    corr = df[cols_num].corr()
    fig, ax = plt.subplots(figsize=(max(6, len(cols_num)), max(5, len(cols_num) - 1)))
    im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    plt.colorbar(im, ax=ax, label="Corrélation")
    ax.set_xticks(range(len(cols_num)))
    ax.set_yticks(range(len(cols_num)))
    ax.set_xticklabels(cols_num, rotation=45, ha='right', fontsize=8)
    ax.set_yticklabels(cols_num, fontsize=8)
    for i in range(len(cols_num)):
        for j in range(len(cols_num)):
            val = corr.iloc[i, j]
            ax.text(j, i, f"{val:.2f}", ha='center', va='center', fontsize=7,
                    color='white' if abs(val) > 0.5 else 'black')
    ax.set_title(f"Matrice de corrélation — {nom}", fontsize=12, fontweight='bold', pad=12)
    plt.tight_layout()
    return fig


# ─── Constantes ─────────────────────────────────────────────────────────────

TYPES_GRAPHE = [
    "Ligne",
    "Scatter",
    "Barres",
    "Histogramme",
    "Boxplot",
    "Aire empilée",
    "Corrélation (heatmap)",
]

# Types qui n'ont pas besoin de col_x
_NO_X = {"Histogramme", "Boxplot", "Corrélation (heatmap)"}
# Types qui n'ont pas besoin de col_y
_NO_Y = {"Corrélation (heatmap)"}
# Types qui filtrent les cols Y sur numériques
_NUM_Y = {"Scatter", "Histogramme", "Boxplot", "Aire empilée"}


# ─── Application principale ─────────────────────────────────────────────────

class CSVComparatorApp(dnd.TkinterDnD.Tk):

    def __init__(self, fichiers_initiaux=None):
        super().__init__()
        self.title("CSV Comparator GUI v2.0")
        self.geometry("1280x800")
        self.minsize(900, 600)

        self.datasets: dict = {}
        self.fig = None
        self.canvas = None
        self.toolbar = None

        self._build_ui()
        self._apply_style()
        self._on_type_change()  # initialise la visibilité des widgets

        if fichiers_initiaux:
            self._load_files(fichiers_initiaux)

    # ── Style ────────────────────────────────────────────────────────────────

    def _apply_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Accent.TButton', foreground='white', background='#2563eb')
        style.map('Accent.TButton', background=[('active', '#1d4ed8')])

    # ── Construction de l'interface ──────────────────────────────────────────

    def _build_ui(self):
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6,
                               sashrelief='raised', bg='#e2e8f0')
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, width=295)
        left.pack_propagate(False)
        paned.add(left, minsize=230)
        self._build_left_panel(left)

        right = ttk.Frame(paned)
        paned.add(right, minsize=400)
        self._build_right_panel(right)

        self.status_var = tk.StringVar(value="Glissez des fichiers CSV ou cliquez sur Ouvrir.")
        ttk.Label(self, textvariable=self.status_var,
                  relief='sunken', anchor='w', padding=(6, 2)).pack(side=tk.BOTTOM, fill=tk.X)

    def _build_left_panel(self, parent):
        pad = {'padx': 8, 'pady': 3}

        # ── Zone drag & drop ────────────────────────────────────────────
        drop_lf = ttk.LabelFrame(parent, text="Fichiers CSV", padding=4)
        drop_lf.pack(fill=tk.X, **pad)

        self.drop_label = tk.Label(
            drop_lf,
            text="Glissez des CSV ici\n── ou ──",
            bg='#f1f5f9', relief='groove', cursor='hand2',
            pady=8, font=('Segoe UI', 9)
        )
        self.drop_label.pack(fill=tk.X, pady=(0, 4))
        self.drop_label.drop_target_register(dnd.DND_FILES)
        self.drop_label.dnd_bind('<<Drop>>', self._on_drop)

        ttk.Button(drop_lf, text="Ouvrir fichier(s)…",
                   command=self._open_dialog).pack(fill=tk.X)

        # ── Liste des fichiers chargés ───────────────────────────────────
        list_lf = ttk.LabelFrame(parent, text="Fichiers chargés", padding=4)
        list_lf.pack(fill=tk.BOTH, expand=True, **pad)

        list_inner = ttk.Frame(list_lf)
        list_inner.pack(fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(list_inner, orient='vertical')
        self.file_listbox = tk.Listbox(
            list_inner, selectmode=tk.EXTENDED,
            yscrollcommand=vsb.set,
            font=('Segoe UI', 9), activestyle='none',
            selectbackground='#bfdbfe'
        )
        vsb.config(command=self.file_listbox.yview)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.bind('<<ListboxSelect>>', self._on_file_select)

        ttk.Button(list_lf, text="Supprimer sélection",
                   command=self._remove_selected).pack(fill=tk.X, pady=(4, 0))

        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=2)

        # ── Contrôles graphe ────────────────────────────────────────────
        graph_lf = ttk.LabelFrame(parent, text="Graphe", padding=4)
        graph_lf.pack(fill=tk.X, **pad)

        ttk.Label(graph_lf, text="Type :").pack(anchor='w')
        self.graph_type_var = tk.StringVar(value=TYPES_GRAPHE[0])
        self.graph_type_cb = ttk.Combobox(
            graph_lf, textvariable=self.graph_type_var,
            values=TYPES_GRAPHE, state='readonly'
        )
        self.graph_type_cb.pack(fill=tk.X, pady=(0, 6))
        self.graph_type_cb.bind('<<ComboboxSelected>>', self._on_type_change)

        # Colonne X
        self.x_frame = ttk.Frame(graph_lf)
        ttk.Label(self.x_frame, text="Colonne X :").pack(anchor='w')
        self.col_x_var = tk.StringVar()
        self.col_x_cb = ttk.Combobox(self.x_frame, textvariable=self.col_x_var,
                                      state='readonly')
        self.col_x_cb.pack(fill=tk.X, pady=(0, 4))

        # Colonne(s) Y
        self.y_frame = ttk.Frame(graph_lf)
        ttk.Label(self.y_frame, text="Colonne(s) Y :").pack(anchor='w')
        y_inner = ttk.Frame(self.y_frame)
        y_inner.pack(fill=tk.X)
        vsb_y = ttk.Scrollbar(y_inner, orient='vertical')
        self.col_y_lb = tk.Listbox(
            y_inner, selectmode=tk.EXTENDED, yscrollcommand=vsb_y.set,
            height=4, font=('Segoe UI', 9), activestyle='none',
            selectbackground='#bfdbfe'
        )
        vsb_y.config(command=self.col_y_lb.yview)
        self.col_y_lb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        vsb_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Bins (histogramme uniquement)
        self.bins_frame = ttk.Frame(graph_lf)
        ttk.Label(self.bins_frame, text="Bins :").pack(side=tk.LEFT)
        self.bins_var = tk.StringVar(value="20")
        ttk.Entry(self.bins_frame, textvariable=self.bins_var, width=6).pack(side=tk.LEFT, padx=4)

        ttk.Button(graph_lf, text="Tracer le graphe",
                   command=self._draw_graph,
                   style='Accent.TButton').pack(fill=tk.X, pady=(8, 2))

        ttk.Separator(parent, orient='horizontal').pack(fill=tk.X, pady=2)

        ttk.Button(parent, text="Exporter / Fusionner CSV",
                   command=self._export_merge).pack(fill=tk.X, padx=8, pady=4)

    def _build_right_panel(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Onglet Graphe
        tab_graphe = ttk.Frame(self.notebook)
        self.notebook.add(tab_graphe, text="  Graphe  ")

        self.canvas_frame = ttk.Frame(tab_graphe)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas_frame.bind('<Configure>', self._on_canvas_resize)

        self.placeholder = ttk.Label(
            self.canvas_frame,
            text="Chargez des CSV\npuis cliquez sur « Tracer le graphe »",
            font=('Segoe UI', 11), foreground='#94a3b8', justify='center'
        )
        self.placeholder.place(relx=0.5, rely=0.5, anchor='center')

        # Onglet Données
        tab_data = ttk.Frame(self.notebook)
        self.notebook.add(tab_data, text="  Données  ")
        self._build_data_tab(tab_data)

    def _build_data_tab(self, parent):
        # Aperçu DataFrame
        preview_lf = ttk.LabelFrame(parent, text="Aperçu (50 premières lignes)", padding=4)
        preview_lf.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        self.preview_tree = ttk.Treeview(preview_lf, show='headings')
        vsb = ttk.Scrollbar(preview_lf, orient='vertical', command=self.preview_tree.yview)
        hsb = ttk.Scrollbar(preview_lf, orient='horizontal', command=self.preview_tree.xview)
        self.preview_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.preview_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        preview_lf.rowconfigure(0, weight=1)
        preview_lf.columnconfigure(0, weight=1)

        # Statistiques
        stats_lf = ttk.LabelFrame(parent, text="Statistiques descriptives", padding=4)
        stats_lf.pack(fill=tk.X, padx=6, pady=(0, 4))

        self.stats_text = tk.Text(stats_lf, height=8, font=('Courier', 8),
                                   state='disabled', wrap='none')
        vsb_s = ttk.Scrollbar(stats_lf, orient='vertical', command=self.stats_text.yview)
        hsb_s = ttk.Scrollbar(stats_lf, orient='horizontal', command=self.stats_text.xview)
        self.stats_text.configure(yscrollcommand=vsb_s.set, xscrollcommand=hsb_s.set)
        self.stats_text.grid(row=0, column=0, sticky='nsew')
        vsb_s.grid(row=0, column=1, sticky='ns')
        hsb_s.grid(row=1, column=0, sticky='ew')
        stats_lf.rowconfigure(0, weight=1)
        stats_lf.columnconfigure(0, weight=1)

    # ── Drag & Drop ─────────────────────────────────────────────────────────

    def _parse_drop_paths(self, raw):
        return [m[0] or m[1]
                for m in re.findall(r'\{([^}]+)\}|([^\s{}]+)', raw)
                if m[0] or m[1]]

    def _on_drop(self, event):
        paths = self._parse_drop_paths(event.data)
        csv_paths = [p for p in paths if p.lower().endswith('.csv')]
        if not csv_paths:
            messagebox.showwarning("Format incorrect", "Seuls les fichiers .csv sont acceptés.")
            return
        self._load_files(csv_paths)

    def _open_dialog(self):
        paths = filedialog.askopenfilenames(
            title="Ouvrir des fichiers CSV",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")]
        )
        if paths:
            self._load_files(list(paths))

    def _load_files(self, paths):
        loaded = 0
        for path in paths:
            p = Path(path)
            try:
                df, sep = charger_csv(path)
                self.datasets[p.stem] = {"df": df, "chemin": str(path), "sep": sep}
                loaded += 1
            except Exception as e:
                messagebox.showerror("Erreur de chargement", str(e))
        if loaded:
            self._refresh_file_list()
            self._status(f"{loaded} fichier(s) chargé(s). Total : {len(self.datasets)}")

    def _refresh_file_list(self):
        self.file_listbox.delete(0, tk.END)
        for nom, d in self.datasets.items():
            df = d["df"]
            self.file_listbox.insert(tk.END, f"{nom}  ({len(df)} lig., {len(df.columns)} col.)")
        if self.file_listbox.size() > 0:
            self.file_listbox.selection_set(0)
            self._on_file_select(None)

    def _remove_selected(self):
        sel = list(self.file_listbox.curselection())
        noms = list(self.datasets.keys())
        for i in reversed(sel):
            if i < len(noms):
                del self.datasets[noms[i]]
        self._refresh_file_list()
        self._status(f"{len(sel)} fichier(s) supprimé(s).")

    # ── Prévisualisation ────────────────────────────────────────────────────

    def _on_file_select(self, event):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        noms = list(self.datasets.keys())
        if sel[0] >= len(noms):
            return
        nom = noms[sel[0]]
        df = self.datasets[nom]["df"]
        self._populate_treeview(df)
        self._show_stats(df)
        self._update_column_selectors(df)

    def _populate_treeview(self, df):
        tree = self.preview_tree
        tree.delete(*tree.get_children())
        cols = list(df.columns.astype(str))
        tree['columns'] = cols
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=max(80, len(col) * 8), minwidth=50)
        for _, row in df.head(50).iterrows():
            tree.insert('', tk.END, values=[str(v) for v in row])

    def _show_stats(self, df):
        stats_str = df.describe().to_string()
        self.stats_text.config(state='normal')
        self.stats_text.delete('1.0', tk.END)
        self.stats_text.insert('1.0', stats_str)
        self.stats_text.config(state='disabled')

    def _update_column_selectors(self, df):
        gtype = self.graph_type_var.get()
        cols_all = list(df.columns.astype(str))
        cols_num = list(df.select_dtypes(include='number').columns.astype(str))

        # Col X
        self.col_x_cb['values'] = cols_all
        if cols_all and not self.col_x_var.get():
            self.col_x_var.set(cols_all[0])

        # Col Y
        y_cols = cols_num if gtype in _NUM_Y else cols_all
        self.col_y_lb.delete(0, tk.END)
        for c in y_cols:
            self.col_y_lb.insert(tk.END, c)
        if self.col_y_lb.size() > 0:
            self.col_y_lb.selection_set(0)

    # ── Contrôles graphe (visibilité dynamique) ──────────────────────────────

    def _on_type_change(self, event=None):
        gtype = self.graph_type_var.get()

        # Masquer tous les widgets conditionnels
        self.x_frame.pack_forget()
        self.y_frame.pack_forget()
        self.bins_frame.pack_forget()

        if gtype == "Histogramme":
            self.y_frame.pack(fill=tk.X)
            self.bins_frame.pack(fill=tk.X, pady=2)
        elif gtype == "Boxplot":
            self.y_frame.pack(fill=tk.X)
        elif gtype == "Corrélation (heatmap)":
            pass  # pas de sélection de colonnes
        else:
            self.x_frame.pack(fill=tk.X)
            self.y_frame.pack(fill=tk.X)

        # Mettre à jour les options de colonnes
        sel = self.file_listbox.curselection()
        noms = list(self.datasets.keys())
        if sel and sel[0] < len(noms):
            self._update_column_selectors(self.datasets[noms[sel[0]]]["df"])

    # ── Tracé graphe ────────────────────────────────────────────────────────

    def _get_selected_dataset_names(self):
        sel = self.file_listbox.curselection()
        noms = list(self.datasets.keys())
        result = [noms[i] for i in sel if i < len(noms)]
        return result if result else noms  # si rien sélectionné, tous

    def _draw_graph(self):
        if not self.datasets:
            messagebox.showwarning("Aucun fichier", "Chargez d'abord un fichier CSV.")
            return

        selection = self._get_selected_dataset_names()
        gtype = self.graph_type_var.get()
        col_x = self.col_x_var.get()
        y_sel = self.col_y_lb.curselection()
        cols_y = [self.col_y_lb.get(i) for i in y_sel]

        try:
            if gtype == "Ligne":
                if not col_x or not cols_y:
                    messagebox.showwarning("Colonnes manquantes",
                                           "Sélectionnez une colonne X et au moins une colonne Y.")
                    return
                fig = build_fig_ligne(self.datasets, selection, col_x, cols_y)

            elif gtype == "Scatter":
                if not col_x or not cols_y:
                    messagebox.showwarning("Colonnes manquantes",
                                           "Sélectionnez une colonne X et au moins une colonne Y.")
                    return
                fig = build_fig_scatter(self.datasets, selection, col_x, cols_y)

            elif gtype == "Barres":
                if not col_x or not cols_y:
                    messagebox.showwarning("Colonnes manquantes",
                                           "Sélectionnez une colonne X et au moins une colonne Y.")
                    return
                fig = build_fig_barres(self.datasets, selection, col_x, cols_y)

            elif gtype == "Histogramme":
                if not cols_y:
                    messagebox.showwarning("Colonne manquante", "Sélectionnez une colonne.")
                    return
                try:
                    bins = int(self.bins_var.get())
                except ValueError:
                    bins = 20
                fig = build_fig_histo(self.datasets, selection, cols_y[0], bins)

            elif gtype == "Boxplot":
                if not cols_y:
                    messagebox.showwarning("Colonnes manquantes",
                                           "Sélectionnez au moins une colonne Y.")
                    return
                fig = build_fig_boxplot(self.datasets, selection, cols_y)

            elif gtype == "Aire empilée":
                if not col_x or not cols_y:
                    messagebox.showwarning("Colonnes manquantes",
                                           "Sélectionnez une colonne X et au moins une colonne Y.")
                    return
                fig = build_fig_aire(self.datasets, selection, col_x, cols_y)

            elif gtype == "Corrélation (heatmap)":
                fig = build_fig_heatmap(self.datasets, selection)

            else:
                return

            self._embed_figure(fig)
            self.notebook.select(0)
            self._status(f"Graphe « {gtype} » tracé.")

        except Exception as e:
            messagebox.showerror("Erreur lors du tracé", str(e))

    def _embed_figure(self, fig):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        if self.toolbar:
            self.toolbar.destroy()
        if self.fig:
            plt.close(self.fig)
        self.placeholder.place_forget()

        self.fig = fig
        self.canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_frame)
        self.toolbar.update()
        self.canvas.draw()

    def _on_canvas_resize(self, event):
        if self.fig and self.canvas and event.width > 50 and event.height > 50:
            try:
                dpi = self.fig.dpi
                self.fig.set_size_inches(event.width / dpi, event.height / dpi)
                self.canvas.draw_idle()
            except Exception:
                pass

    # ── Export ──────────────────────────────────────────────────────────────

    def _export_merge(self):
        if not self.datasets:
            messagebox.showwarning("Aucun fichier", "Chargez d'abord des fichiers CSV.")
            return
        path = filedialog.asksaveasfilename(
            title="Enregistrer le CSV fusionné",
            defaultextension=".csv",
            filetypes=[("Fichiers CSV", "*.csv")]
        )
        if not path:
            return
        dfs = [d["df"].assign(_source=nom) for nom, d in self.datasets.items()]
        merged = pd.concat(dfs, ignore_index=True)
        merged.to_csv(path, index=False)
        self._status(f"Exporté : {Path(path).name}  ({len(merged)} lignes)")

    # ── Utilitaires ─────────────────────────────────────────────────────────

    def _status(self, msg):
        self.status_var.set(msg)


# ─── Point d'entrée ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CSV Comparator GUI v2.0")
    parser.add_argument("fichiers", nargs="*", help="Fichiers CSV à charger au démarrage")
    args = parser.parse_args()
    app = CSVComparatorApp(fichiers_initiaux=args.fichiers if args.fichiers else None)
    app.mainloop()


if __name__ == "__main__":
    main()

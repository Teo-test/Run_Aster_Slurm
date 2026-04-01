#!/usr/bin/env python3
"""
PPTX Chart Extractor GUI — Interface graphique avec drag & drop
Usage: python pptx_chart_extractor_gui.py [fichier.pptx] [-o dossier_sortie]

Dépendance supplémentaire : pip install tkinterdnd2
"""

import sys
import re
import argparse
import zipfile
import xml.etree.ElementTree as ET
import threading
from pathlib import Path, PurePosixPath

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


# ─── Namespaces XML Office Open ──────────────────────────────────────────────

NS = {
    'c':   'http://schemas.openxmlformats.org/drawingml/2006/chart',
    'a':   'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p':   'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r':   'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
}

CHART_TAGS = {
    'lineChart':      'ligne',
    'line3DChart':    'ligne',
    'barChart':       'barres',
    'bar3DChart':     'barres',
    'scatterChart':   'scatter',
    'bubbleChart':    'scatter',
    'pieChart':       'pie',
    'pie3DChart':     'pie',
    'doughnutChart':  'pie',
    'areaChart':      'aire',
    'area3DChart':    'aire',
    'radarChart':     'radar',
    'stockChart':     'ligne',
    'surfaceChart':   'surface',
    'surface3DChart': 'surface',
}


# ─── Fonctions de traitement XML (copiées de pptx_chart_extractor.py) ────────

def slugify(texte):
    texte = re.sub(r'[^\w\s-]', '', str(texte).lower())
    return re.sub(r'[\s-]+', '_', texte).strip('_') or "graphe"


def couleurs(n):
    return cm.tab10(np.linspace(0, 0.9, max(n, 1)))


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


def extraire_serie_classique(ser_el):
    nom     = lire_nom_serie(ser_el) or "Série"
    cats, _ = lire_ref(ser_el.find('c:cat', NS))
    vals, _ = lire_ref(ser_el.find('c:val', NS))
    vals    = [to_float(v) for v in vals]
    return nom, cats, vals


def extraire_serie_scatter(ser_el):
    nom   = lire_nom_serie(ser_el) or "Série"
    xs, _ = lire_ref(ser_el.find('c:xVal', NS))
    ys, _ = lire_ref(ser_el.find('c:yVal', NS))
    xs    = [to_float(v) for v in xs]
    ys    = [to_float(v) for v in ys]
    return nom, xs, ys


def construire_df_classique(series_data):
    if not series_data:
        return pd.DataFrame()
    df_dict = {}
    max_len = 0
    for nom, cats, vals in series_data:
        xs = ([str(c) if c is not None else "" for c in cats]
              if cats else [str(i) for i in range(len(vals))])
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


def charger_rels(zf, rels_path):
    if rels_path not in zf.namelist():
        return {}
    tree = ET.fromstring(zf.read(rels_path))
    return {rel.get('Id'): rel.get('Target') for rel in tree}


def resoudre_chart_path(slide_path, target):
    """
    Résout le chemin relatif d'un chart dans le ZIP.
    Utilise PurePosixPath (compatible Windows) pour rester dans l'espace ZIP.
    """
    base   = PurePosixPath(slide_path).parent
    parts  = []
    for part in (base / PurePosixPath(target)).parts:
        if part == '..':
            if parts:
                parts.pop()
        elif part != '.':
            parts.append(part)
    return '/'.join(parts)


def analyser_pptx(chemin_pptx):
    """Parcourt toutes les slides et extrait chaque graphe."""
    graphes    = []
    graphe_idx = 0
    with zipfile.ZipFile(chemin_pptx, 'r') as zf:
        noms = set(zf.namelist())
        slides = sorted(
            [n for n in noms if re.match(r'ppt/slides/slide\d+\.xml$', n)],
            key=lambda x: int(re.search(r'\d+', x).group())
        )
        for slide_path in slides:
            slide_num   = int(re.search(r'\d+', slide_path).group())
            slide_tree  = ET.fromstring(zf.read(slide_path))
            titre_slide = lire_titre_slide(slide_tree)
            rels_path   = re.sub(
                r'slides/(slide\d+\.xml)$',
                r'slides/_rels/\1.rels',
                slide_path
            )
            rels = charger_rels(zf, rels_path)
            for rId, target in rels.items():
                if 'chart' not in target.lower():
                    continue
                chart_path = resoudre_chart_path(slide_path, target)
                if chart_path not in noms:
                    chart_path = 'ppt/charts/' + Path(target).name
                if chart_path not in noms:
                    continue
                chart_tree  = ET.fromstring(zf.read(chart_path))
                titre_chart = lire_titre_chart(chart_tree)
                famille, tag = detecter_famille(chart_tree)
                df, _, _     = extraire_chart(chart_tree)
                graphe_idx  += 1
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


# ─── Fonctions de plot (adaptées pour retourner fig) ─────────────────────────

def style_ax(ax, titre_graphe, xlabel="", ylabel=""):
    ax.set_title(titre_graphe, fontsize=12, fontweight='bold', pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, alpha=0.25, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


def plot_graphe_gui(g):
    """Construit et retourne la figure matplotlib pour le graphe g."""
    df      = g["df"]
    famille = g["famille"]
    titre_g = g["titre"]
    fig, ax = plt.subplots(figsize=(9, 5))

    if df.empty:
        ax.text(0.5, 0.5, "Données non disponibles", ha='center', va='center',
                transform=ax.transAxes, fontsize=14, color='gray')
        ax.set_title(titre_g, fontsize=12, fontweight='bold')
        plt.tight_layout()
        return fig

    cols_x      = [c for c in df.columns if str(c).endswith('_X')]
    series_noms = [c[:-2] for c in cols_x]
    clrs        = couleurs(max(len(series_noms), 1))

    if famille == 'scatter':
        for i, nom in enumerate(series_noms):
            xs = pd.to_numeric(df[f"{nom}_X"], errors='coerce')
            ys = pd.to_numeric(df[f"{nom}_Y"], errors='coerce')
            ax.scatter(xs, ys, label=nom, color=clrs[i],
                       alpha=0.75, s=45, edgecolors='none')
        style_ax(ax, titre_g, "X", "Y")
        if len(series_noms) > 1:
            ax.legend(fontsize=8)

    elif famille == 'pie':
        if series_noms:
            nom      = series_noms[0]
            labs     = df[f"{nom}_X"].dropna()
            vals_num = pd.to_numeric(df[f"{nom}_Y"], errors='coerce').dropna()
            idx_vals = vals_num.index
            try:
                pie_labels = labs.iloc[idx_vals] if len(labs) > max(idx_vals, default=0) else labs
            except Exception:
                pie_labels = labs
            ax.pie(vals_num, labels=pie_labels, autopct='%1.1f%%', startangle=90,
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
            ax.bar(x + offset, vals, width=w * 0.92,
                   label=nom, color=clrs[i], alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, rotation=30, ha='right', fontsize=8)
        style_ax(ax, titre_g, "", "Valeur")
        if n > 1:
            ax.legend(fontsize=8)

    else:  # ligne, aire, radar, surface, inconnu
        x_labels = df[f"{series_noms[0]}_X"].fillna("").tolist() if series_noms else []
        x = np.arange(len(df))
        for i, nom in enumerate(series_noms):
            vals = pd.to_numeric(df[f"{nom}_Y"], errors='coerce')
            if famille == 'aire':
                ax.fill_between(x, vals, alpha=0.35, color=clrs[i])
            ax.plot(x, vals, label=nom, color=clrs[i],
                    linewidth=1.8, marker='o', markersize=3)
        ax.set_xticks(x)
        ax.set_xticklabels(x_labels, rotation=30, ha='right', fontsize=8)
        style_ax(ax, titre_g, "", "Valeur")
        if len(series_noms) > 1:
            ax.legend(fontsize=8)

    plt.tight_layout()
    return fig


def plot_graphe_sauvegarder(g, dossier_out):
    """Sauvegarde le graphe en PNG dans dossier_out. Retourne le chemin du fichier."""
    fig     = plot_graphe_gui(g)
    dossier = Path(dossier_out)
    dossier.mkdir(parents=True, exist_ok=True)
    nom     = f"graphe_{g['idx']:02d}_{slugify(g['titre'])}.png"
    chemin  = dossier / nom
    fig.savefig(chemin, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return chemin


def exporter_csv_gui(graphes, selection, dossier_out):
    """Exporte les graphes sélectionnés en CSV. Retourne la liste des chemins créés."""
    dossier  = Path(dossier_out)
    dossier.mkdir(parents=True, exist_ok=True)
    exportes = []
    for idx in selection:
        g = graphes[idx]
        if g["df"].empty:
            continue
        nom    = f"graphe_{g['idx']:02d}_{slugify(g['titre'])}.csv"
        chemin = dossier / nom
        g["df"].to_csv(chemin, index=False, encoding="utf-8-sig")
        exportes.append(chemin)
    return exportes


# ─── Application principale ─────────────────────────────────────────────────

class PPTXExtractorApp(dnd.TkinterDnD.Tk):

    def __init__(self, chemin_initial=None, dossier_out="pptx_export"):
        super().__init__()
        self.title("PPTX Chart Extractor GUI v2.0")
        self.geometry("1400x850")
        self.minsize(1000, 650)

        self.graphes: list     = []
        self.chemin_pptx       = None
        self.checked: dict     = {}   # {list_index: bool}

        self.fig     = None
        self.canvas  = None
        self.toolbar = None

        self._build_ui()
        self._apply_style()

        # Initialiser le champ dossier sortie
        self.out_var.set(dossier_out)

        if chemin_initial:
            self.after(100, lambda: self._load_pptx(chemin_initial))

    # ── Style ────────────────────────────────────────────────────────────────

    def _apply_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Accent.TButton', foreground='white', background='#2563eb')
        style.map('Accent.TButton', background=[('active', '#1d4ed8')])
        style.configure('Green.TButton', foreground='white', background='#16a34a')
        style.map('Green.TButton', background=[('active', '#15803d')])

    # ── Construction de l'interface ──────────────────────────────────────────

    def _build_ui(self):
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6,
                               sashrelief='raised', bg='#e2e8f0')
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, width=345)
        left.pack_propagate(False)
        paned.add(left, minsize=270)
        self._build_left_panel(left)

        right = ttk.Frame(paned)
        paned.add(right, minsize=500)
        self._build_right_panel(right)

        # Barre de statut + progressbar
        bottom = ttk.Frame(self)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar(value="Glissez un fichier .pptx ou cliquez sur Ouvrir.")
        ttk.Label(bottom, textvariable=self.status_var,
                  relief='sunken', anchor='w', padding=(6, 2)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progressbar = ttk.Progressbar(bottom, mode='indeterminate', length=120)
        self.progressbar.pack(side=tk.RIGHT, padx=6, pady=2)

    def _build_left_panel(self, parent):
        pad = {'padx': 8, 'pady': 3}

        # ── Zone drag & drop ────────────────────────────────────────────
        drop_lf = ttk.LabelFrame(parent, text="Fichier PPTX", padding=4)
        drop_lf.pack(fill=tk.X, **pad)

        self.drop_label = tk.Label(
            drop_lf,
            text="Glissez un fichier .pptx ici\n── ou ──",
            bg='#f1f5f9', relief='groove', cursor='hand2',
            pady=8, font=('Segoe UI', 9)
        )
        self.drop_label.pack(fill=tk.X, pady=(0, 4))
        self.drop_label.drop_target_register(dnd.DND_FILES)
        self.drop_label.dnd_bind('<<Drop>>', self._on_drop)

        ttk.Button(drop_lf, text="Ouvrir un fichier PPTX…",
                   command=self._open_dialog).pack(fill=tk.X)

        self.file_label = ttk.Label(drop_lf, text="Aucun fichier chargé",
                                     foreground='#64748b', wraplength=290)
        self.file_label.pack(fill=tk.X, pady=(4, 0))

        # ── Dossier de sortie ───────────────────────────────────────────
        out_lf = ttk.LabelFrame(parent, text="Dossier de sortie", padding=4)
        out_lf.pack(fill=tk.X, **pad)

        out_inner = ttk.Frame(out_lf)
        out_inner.pack(fill=tk.X)
        self.out_var = tk.StringVar()
        ttk.Entry(out_inner, textvariable=self.out_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_inner, text="…", width=3,
                   command=self._choose_output_dir).pack(side=tk.RIGHT, padx=(4, 0))

        # ── Liste des graphes ───────────────────────────────────────────
        list_lf = ttk.LabelFrame(parent, text="Graphes détectés", padding=4)
        list_lf.pack(fill=tk.BOTH, expand=True, **pad)

        cols = ('check', 'num', 'slide', 'type', 'titre')
        self.chart_tree = ttk.Treeview(list_lf, columns=cols, show='headings',
                                        selectmode='browse')
        self.chart_tree.heading('check', text='☑')
        self.chart_tree.heading('num',   text='N°')
        self.chart_tree.heading('slide', text='Slide')
        self.chart_tree.heading('type',  text='Type')
        self.chart_tree.heading('titre', text='Titre')
        self.chart_tree.column('check', width=30,  stretch=False, anchor='center')
        self.chart_tree.column('num',   width=30,  stretch=False, anchor='center')
        self.chart_tree.column('slide', width=42,  stretch=False, anchor='center')
        self.chart_tree.column('type',  width=65,  stretch=False)
        self.chart_tree.column('titre', width=140)

        vsb = ttk.Scrollbar(list_lf, orient='vertical', command=self.chart_tree.yview)
        self.chart_tree.configure(yscrollcommand=vsb.set)
        self.chart_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        list_lf.rowconfigure(0, weight=1)
        list_lf.columnconfigure(0, weight=1)

        self.chart_tree.bind('<<TreeviewSelect>>', self._on_chart_select)
        self.chart_tree.bind('<ButtonRelease-1>', self._on_tree_click)

        # Boutons sélection
        sel_frame = ttk.Frame(list_lf)
        sel_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(4, 0))
        ttk.Button(sel_frame, text="Tout ☑", command=self._select_all,  width=9).pack(side=tk.LEFT)
        ttk.Button(sel_frame, text="Tout ☐", command=self._deselect_all, width=9).pack(side=tk.LEFT, padx=4)

        # ── Boutons export ──────────────────────────────────────────────
        export_lf = ttk.LabelFrame(parent, text="Export", padding=4)
        export_lf.pack(fill=tk.X, **pad)

        ttk.Button(export_lf, text="Export CSV (cochés)",
                   command=self._export_csv_selection).pack(fill=tk.X, pady=1)
        ttk.Button(export_lf, text="Export PNG (cochés)",
                   command=self._export_png_selection).pack(fill=tk.X, pady=1)
        ttk.Button(export_lf, text="Export complet (tous → CSV + PNG)",
                   command=self._export_all,
                   style='Green.TButton').pack(fill=tk.X, pady=(4, 1))

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
            text="Chargez un fichier .pptx\npuis sélectionnez un graphe dans la liste",
            font=('Segoe UI', 12), foreground='#94a3b8', justify='center'
        )
        self.placeholder.place(relx=0.5, rely=0.5, anchor='center')

        # Onglet Données
        tab_data = ttk.Frame(self.notebook)
        self.notebook.add(tab_data, text="  Données  ")
        self._build_data_tab(tab_data)

        # Onglet Détail XML
        tab_detail = ttk.Frame(self.notebook)
        self.notebook.add(tab_detail, text="  Détail XML  ")
        self._build_detail_tab(tab_detail)

    def _build_data_tab(self, parent):
        self.data_tree = ttk.Treeview(parent, show='headings')
        vsb = ttk.Scrollbar(parent, orient='vertical',   command=self.data_tree.yview)
        hsb = ttk.Scrollbar(parent, orient='horizontal', command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.data_tree.grid(row=0, column=0, sticky='nsew', padx=(6, 0), pady=6)
        vsb.grid(row=0, column=1, sticky='ns',  pady=6)
        hsb.grid(row=1, column=0, sticky='ew',  padx=(6, 0))
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

    def _build_detail_tab(self, parent):
        self.detail_text = tk.Text(parent, font=('Courier', 9), state='disabled',
                                    wrap='none', padx=8, pady=8)
        vsb = ttk.Scrollbar(parent, orient='vertical',   command=self.detail_text.yview)
        hsb = ttk.Scrollbar(parent, orient='horizontal', command=self.detail_text.xview)
        self.detail_text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.detail_text.grid(row=0, column=0, sticky='nsew', padx=(6, 0), pady=6)
        vsb.grid(row=0, column=1, sticky='ns',  pady=6)
        hsb.grid(row=1, column=0, sticky='ew',  padx=(6, 0))
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

    # ── Drag & Drop ─────────────────────────────────────────────────────────

    def _parse_drop_paths(self, raw):
        return [m[0] or m[1]
                for m in re.findall(r'\{([^}]+)\}|([^\s{}]+)', raw)
                if m[0] or m[1]]

    def _on_drop(self, event):
        paths = self._parse_drop_paths(event.data)
        pptx_paths = [p for p in paths if p.lower().endswith('.pptx')]
        if not pptx_paths:
            messagebox.showwarning("Format incorrect", "Seuls les fichiers .pptx sont acceptés.")
            return
        self._load_pptx(pptx_paths[0])

    def _open_dialog(self):
        path = filedialog.askopenfilename(
            title="Ouvrir un fichier PPTX",
            filetypes=[("Présentations PowerPoint", "*.pptx"), ("Tous les fichiers", "*.*")]
        )
        if path:
            self._load_pptx(path)

    def _choose_output_dir(self):
        d = filedialog.askdirectory(title="Choisir le dossier de sortie")
        if d:
            self.out_var.set(d)

    # ── Chargement PPTX ─────────────────────────────────────────────────────

    def _load_pptx(self, chemin):
        if not Path(chemin).exists():
            messagebox.showerror("Fichier introuvable", str(chemin))
            return
        if not zipfile.is_zipfile(chemin):
            messagebox.showerror("Fichier invalide",
                                  f"{Path(chemin).name} n'est pas un fichier PPTX valide.")
            return

        self.chemin_pptx = chemin
        self.file_label.config(text=Path(chemin).name)
        self._status(f"Analyse de {Path(chemin).name}…")
        self.progressbar.start(10)

        def worker():
            try:
                graphes = analyser_pptx(chemin)
                self.after(0, self._on_load_complete, graphes, None)
            except Exception as e:
                self.after(0, self._on_load_complete, None, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_load_complete(self, graphes, error):
        self.progressbar.stop()

        if error:
            messagebox.showerror("Erreur d'analyse", f"Impossible d'analyser le fichier :\n{error}")
            self._status("Erreur lors de l'analyse.")
            return

        self.graphes = graphes
        self.checked = {i: True for i in range(len(graphes))}
        self._refresh_chart_list()

        n = len(graphes)
        self.file_label.config(text=f"{Path(self.chemin_pptx).name}  ({n} graphe(s))")
        self._status(f"{n} graphe(s) détecté(s).")

    # ── Liste des graphes ────────────────────────────────────────────────────

    def _refresh_chart_list(self):
        self.chart_tree.delete(*self.chart_tree.get_children())
        for i, g in enumerate(self.graphes):
            check = '☑' if self.checked.get(i, True) else '☐'
            vide  = ' ⚠' if g["df"].empty else ''
            self.chart_tree.insert('', tk.END, iid=str(i), values=(
                check,
                g['idx'],
                g['slide'],
                g['famille'],
                g['titre'][:42] + vide,
            ))

    def _on_tree_click(self, event):
        """Bascule la case à cocher au clic sur la colonne ☑."""
        col = self.chart_tree.identify_column(event.x)
        row = self.chart_tree.identify_row(event.y)
        if col == '#1' and row:
            i = int(row)
            self.checked[i] = not self.checked.get(i, True)
            self._refresh_chart_list()
            self.chart_tree.selection_set(row)

    def _on_chart_select(self, event):
        sel = self.chart_tree.selection()
        if not sel:
            return
        i = int(sel[0])
        if i < len(self.graphes):
            g = self.graphes[i]
            self._show_chart_preview(g)
            self._show_data_preview(g)
            self._show_detail(g)

    def _select_all(self):
        self.checked = {i: True for i in range(len(self.graphes))}
        self._refresh_chart_list()

    def _deselect_all(self):
        self.checked = {i: False for i in range(len(self.graphes))}
        self._refresh_chart_list()

    # ── Prévisualisation ────────────────────────────────────────────────────

    def _show_chart_preview(self, g):
        try:
            fig = plot_graphe_gui(g)
            self._embed_figure(fig)
            self.notebook.select(0)
        except Exception as e:
            self._status(f"Erreur prévisualisation : {e}")

    def _show_data_preview(self, g):
        tree = self.data_tree
        tree.delete(*tree.get_children())
        df = g["df"]
        if df.empty:
            tree['columns'] = ('info',)
            tree.heading('info', text='Info')
            tree.column('info', width=300)
            tree.insert('', tk.END, values=("Aucune donnée extractible pour ce graphe.",))
            return
        cols = list(df.columns.astype(str))
        tree['columns'] = cols
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=max(70, len(col) * 7), minwidth=50)
        for _, row in df.head(100).iterrows():
            tree.insert('', tk.END, values=[str(v) if v is not None else '' for v in row])

    def _show_detail(self, g):
        df          = g["df"]
        cols_x      = [c for c in df.columns if str(c).endswith('_X')] if not df.empty else []
        series_noms = [c[:-2] for c in cols_x]
        lines = [
            f"Titre      : {g['titre']}",
            f"Slide      : {g['slide']}",
            f"Famille    : {g['famille']}",
            f"Balise XML : {g['tag_xml']}",
            f"Chemin ZIP : {g['chart_path']}",
            "",
            f"Lignes     : {len(df) if not df.empty else 'N/A'}",
            f"Séries     : {', '.join(series_noms) if series_noms else 'Aucune'}",
            f"Colonnes   : {', '.join(str(c) for c in df.columns) if not df.empty else 'N/A'}",
        ]
        self.detail_text.config(state='normal')
        self.detail_text.delete('1.0', tk.END)
        self.detail_text.insert('1.0', '\n'.join(lines))
        self.detail_text.config(state='disabled')

    def _embed_figure(self, fig):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        if self.toolbar:
            self.toolbar.destroy()
        if self.fig:
            plt.close(self.fig)
        self.placeholder.place_forget()

        self.fig    = fig
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

    def _get_checked_indices(self):
        return [i for i in range(len(self.graphes)) if self.checked.get(i, True)]

    @property
    def _dossier_out(self):
        return self.out_var.get().strip() or "pptx_export"

    def _export_csv_selection(self):
        if not self.graphes:
            messagebox.showwarning("Aucun graphe", "Chargez d'abord un fichier PPTX.")
            return
        indices = self._get_checked_indices()
        if not indices:
            messagebox.showwarning("Aucune sélection", "Cochez au moins un graphe (colonne ☑).")
            return
        chemins = exporter_csv_gui(self.graphes, indices, self._dossier_out)
        if chemins:
            messagebox.showinfo("Export CSV",
                                f"{len(chemins)} fichier(s) exporté(s) dans :\n{self._dossier_out}")
            self._status(f"{len(chemins)} CSV exporté(s).")
        else:
            messagebox.showwarning("Export vide", "Aucun graphe coché n'avait de données à exporter.")

    def _export_png_selection(self):
        if not self.graphes:
            messagebox.showwarning("Aucun graphe", "Chargez d'abord un fichier PPTX.")
            return
        indices   = self._get_checked_indices()
        non_vides = [i for i in indices if not self.graphes[i]["df"].empty]
        if not non_vides:
            messagebox.showwarning("Export vide",
                                    "Aucun graphe coché n'avait de données à exporter.")
            return
        self._status(f"Export PNG en cours… ({len(non_vides)} graphe(s))")
        chemins = []
        for i in non_vides:
            try:
                c = plot_graphe_sauvegarder(self.graphes[i], self._dossier_out)
                chemins.append(c)
            except Exception as e:
                self._status(f"Erreur graphe {i + 1} : {e}")
        if chemins:
            messagebox.showinfo("Export PNG",
                                f"{len(chemins)} image(s) exportée(s) dans :\n{self._dossier_out}")
            self._status(f"{len(chemins)} PNG exporté(s).")

    def _export_all(self):
        if not self.graphes:
            messagebox.showwarning("Aucun graphe", "Chargez d'abord un fichier PPTX.")
            return
        non_vides = [i for i, g in enumerate(self.graphes) if not g["df"].empty]
        if not non_vides:
            messagebox.showwarning("Export vide", "Aucun graphe n'a de données extractibles.")
            return
        self._status(f"Export complet en cours… ({len(non_vides)} graphe(s))")
        csv_chemins = exporter_csv_gui(self.graphes, non_vides, self._dossier_out)
        png_chemins = []
        for i in non_vides:
            try:
                c = plot_graphe_sauvegarder(self.graphes[i], self._dossier_out)
                png_chemins.append(c)
            except Exception as e:
                self._status(f"Erreur graphe {i + 1} : {e}")
        messagebox.showinfo(
            "Export complet",
            f"{len(csv_chemins)} CSV  +  {len(png_chemins)} PNG\n"
            f"exportés dans : {self._dossier_out}"
        )
        self._status(f"Export complet : {len(csv_chemins)} CSV, {len(png_chemins)} PNG.")

    # ── Utilitaires ─────────────────────────────────────────────────────────

    def _status(self, msg):
        self.status_var.set(msg)


# ─── Point d'entrée ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PPTX Chart Extractor GUI v2.0")
    parser.add_argument("fichier", nargs="?", help="Fichier .pptx à analyser au démarrage")
    parser.add_argument("-o", "--output", default="pptx_export",
                        help="Dossier de sortie (défaut : pptx_export)")
    args = parser.parse_args()
    app  = PPTXExtractorApp(
        chemin_initial=args.fichier,
        dossier_out=args.output
    )
    app.mainloop()


if __name__ == "__main__":
    main()

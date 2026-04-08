"""
================================================================================
  PANDAS read_csv – CHEAT SHEET
  pip install pandas matplotlib openpyxl pyarrow
================================================================================
"""

import pandas as pd
import matplotlib.pyplot as plt

# ==============================================================================
# 1. LECTURE DE BASE
# ==============================================================================

df = pd.read_csv("data.csv")                          # lecture minimale
df = pd.read_csv("/chemin/absolu/data.csv")           # chemin absolu
df = pd.read_csv("https://example.com/data.csv")      # depuis une URL
df = pd.read_csv("data.csv.gz", compression="gzip")   # fichier compressé

# ==============================================================================
# 2. SÉPARATEUR & ENCODAGE
# ==============================================================================

df = pd.read_csv("data.csv", sep=";")                 # CSV français (;)
df = pd.read_csv("data.tsv", sep="\t")                # tabulation
df = pd.read_csv("data.txt", sep=r"\s+")              # espaces multiples (regex)
df = pd.read_csv("data.csv", encoding="utf-8")        # encodage UTF-8
df = pd.read_csv("data.csv", encoding="latin-1")      # accents français (ISO-8859-1)

# ==============================================================================
# 3. EN-TÊTES & INDEX
# ==============================================================================

df = pd.read_csv("data.csv", header=None,
                 names=["id", "nom", "valeur"])        # colonnes personnalisées
df = pd.read_csv("data.csv", header=1)                 # header sur la 2e ligne
df = pd.read_csv("data.csv", index_col="id")           # colonne comme index (nom)
df = pd.read_csv("data.csv", index_col=0)              # colonne comme index (pos)

# ==============================================================================
# 4. SÉLECTION COLONNES & LIGNES
# ==============================================================================

df = pd.read_csv("data.csv", usecols=["nom", "valeur"])  # seulement ces colonnes
df = pd.read_csv("data.csv", skiprows=3)                  # ignorer les 3 premières lignes
df = pd.read_csv("data.csv", nrows=1000)                  # lire seulement 1000 lignes
df = pd.read_csv("data.csv", skipfooter=2, engine="python")  # ignorer les 2 dernières

# ==============================================================================
# 5. TYPES & VALEURS MANQUANTES
# ==============================================================================

df = pd.read_csv("data.csv", dtype={"id": int, "code": str})   # forcer les types
df = pd.read_csv("data.csv", na_values=["N/A", "?", "-", ""])  # valeurs → NaN
df = pd.read_csv("data.csv", keep_default_na=False)             # désactiver NaN auto
df = pd.read_csv("data.csv", parse_dates=["date_achat"])        # parser en datetime

# ==============================================================================
# 6. LECTURE PAR CHUNKS (gros fichiers)
# ==============================================================================

# Itérer par blocs
for chunk in pd.read_csv("big.csv", chunksize=10_000):
    print(chunk.shape)  # traiter chaque bloc

# Concaténer des chunks filtrés
df = pd.concat(
    [c[c["valeur"] > 0] for c in pd.read_csv("big.csv", chunksize=10_000)]
)

# ==============================================================================
# 7. AFFICHAGE & INSPECTION
# ==============================================================================

print(df.head(5))           # 5 premières lignes
print(df.tail(5))           # 5 dernières lignes
print(df.sample(10))        # 10 lignes aléatoires

df.info()                   # types, nulls, mémoire utilisée
print(df.describe())        # stats descriptives (numériques)
print(df.describe(include="all"))  # toutes colonnes

print(df.shape)             # (nb_lignes, nb_colonnes)
print(df.columns.tolist())  # liste des colonnes
print(df.dtypes)            # type de chaque colonne
print(df.isnull().sum())    # nombre de NaN par colonne

# Affichage sans troncature
with pd.option_context("display.max_rows", None, "display.max_columns", None):
    print(df)

# ==============================================================================
# 8. FILTRAGE & SÉLECTION
# ==============================================================================

# Sélection de colonnes
sub = df[["nom", "valeur"]]
sub = df.loc[:, "nom":"valeur"]                        # slice par nom

# Filtres booléens
filtre = df[df["valeur"] > 100]
filtre = df[(df["cat"] == "A") & (df["valeur"] > 0)]
filtre = df[df["pays"].isin(["FR", "DE"])]
filtre = df[~df["pays"].isin(["FR"])]                  # négation

# query() – syntaxe lisible
filtre = df.query("valeur > 100 and cat == 'A'")

# Supprimer les doublons
df = df.drop_duplicates(subset=["id"])

# ==============================================================================
# 9. NETTOYAGE DES DONNÉES
# ==============================================================================

# Valeurs manquantes
df = df.dropna()                                       # supprimer lignes avec NaN
df = df.dropna(subset=["valeur"])                      # seulement sur une colonne
df = df.fillna(0)                                      # remplacer NaN par 0
df["col"] = df["col"].fillna(df["col"].mean())         # remplacer par la moyenne

# Renommer & typer
df = df.rename(columns={"old_name": "new_name"})
df["valeur"] = df["valeur"].astype(float)

# Nettoyage de strings
df["nom"] = df["nom"].str.strip().str.lower()
df["nom"] = df["nom"].str.replace(r"\s+", " ", regex=True)

# Réindexer
df = df.reset_index(drop=True)

# ==============================================================================
# 10. AGRÉGATION & GROUPBY
# ==============================================================================

# Statistiques de base
print(df["valeur"].mean())
print(df["valeur"].value_counts())

# Groupby simple
print(df.groupby("cat")["valeur"].mean())

# Multi-agrégation
result = df.groupby("cat").agg(
    moy=("valeur", "mean"),
    total=("valeur", "sum"),
    nb=("valeur", "count"),
    max=("valeur", "max"),
)
print(result)

# Pivot table
pivot = pd.pivot_table(df, values="valeur", index="cat", aggfunc="sum")
print(pivot)

# ==============================================================================
# 11. VISUALISATION RAPIDE
# ==============================================================================

# Histogramme
df["valeur"].hist(bins=30)
plt.title("Distribution de valeur")
plt.show()

# Courbe temporelle
df.plot(x="date", y="valeur", title="Évolution")
plt.show()

# Barplot groupé
df.groupby("cat")["valeur"].sum().plot(kind="bar", color="steelblue")
plt.title("Total par catégorie")
plt.tight_layout()
plt.show()

# Scatter
df.plot.scatter(x="x", y="y", alpha=0.5)
plt.show()

# Matrice de corrélation (requiert seaborn)
# import seaborn as sns
# sns.heatmap(df.corr(), annot=True, cmap="coolwarm")
# plt.show()

# ==============================================================================
# 12. EXPORT
# ==============================================================================

df.to_csv("output.csv", index=False)                          # CSV
df.to_csv("output.csv", index=False, sep=";", encoding="utf-8-sig")  # CSV français Excel
df.to_excel("output.xlsx", index=False)                       # Excel (pip install openpyxl)
df.to_json("output.json", orient="records", force_ascii=False) # JSON
df.to_parquet("output.parquet")                               # Parquet (pip install pyarrow)

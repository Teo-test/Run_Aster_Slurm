# utils_comparaison.py
# A placer dans votre dossier work
# Import dans le .comm : exec(open('/chemin/work/utils_comparaison.py').read())

import numpy as np
import os
import csv

# ============================================================
# COULEURS
# ============================================================

class c:
    reset  = '\033[0m'
    bold   = '\033[1m'
    red    = '\033[91m'
    yellow = '\033[93m'
    green  = '\033[92m'
    cyan   = '\033[96m'
    white  = '\033[97m'
    blue   = '\033[94m'

# ============================================================
# FONCTIONS D'ERREUR
# ============================================================

def von_mises(sig):
    sxx, syy, szz = sig[:,0], sig[:,1], sig[:,2]
    sxy, sxz, syz = sig[:,3], sig[:,4], sig[:,5]
    return np.sqrt(0.5 * (
        (sxx-syy)**2 + (syy-szz)**2 + (szz-sxx)**2
        + 6*(sxy**2 + sxz**2 + syz**2)
    ))

def erreur_L1(a, r):
    return 100. * np.sum(np.abs(a - r)) / np.sum(np.abs(r))

def erreur_L2(a, r):
    return 100. * np.linalg.norm(a - r) / np.linalg.norm(r)

def erreur_Linf(a, r):
    return 100. * np.max(np.abs(a - r)) / np.max(np.abs(r))

def rmse(a, r):
    return float(np.sqrt(np.mean((a - r)**2)))

def biais(a, r):
    return float(np.mean(a - r))

# ============================================================
# EXTRACTION CHAMPS
# ============================================================

def extraire_champs(resu, n_comp_sig=6, n_comp_dep=3):
    """
    Extrait sig et dep depuis un concept evol_noli.
    Retourne sig (N, n_comp_sig), dep (N, n_comp_dep), vm (N,)
    """
    num = int(resu.getAccessParameters()['NUME_ORDRE'][-1])
    sig = np.array(resu.getField('SIGM_NOEU', num).getValues()).reshape(-1, n_comp_sig)
    dep = np.array(resu.getField('DEPL',      num).getValues()).reshape(-1, n_comp_dep)
    vm  = von_mises(sig)
    return sig, dep, vm

# ============================================================
# CLASSE RAPPORT
# ============================================================

class Rapport:

    @staticmethod
    def entete(titre):
        print(c.cyan + '=' * 80 + c.reset)
        print(c.bold + titre.center(80) + c.reset)
        print(c.cyan + '=' * 80 + c.reset)

    @staticmethod
    def separateur():
        print(c.blue + '-' * 80 + c.reset)

    @staticmethod
    def parametre(valeur_param):
        print(f"\n{c.bold}{c.white}Parametre teste : {c.yellow}{valeur_param}{c.reset}")
        Rapport.separateur()
        print(f"{c.bold}"
              f"{'Grandeur':<20s} | "
              f"{'L2':>8s} | "
              f"{'Linf':>8s} | "
              f"{'L1':>8s} | "
              f"{'RMSE':>12s} | "
              f"{'Biais':>12s}"
              f"{c.reset}")
        Rapport.separateur()

    @staticmethod
    def ligne(label, a, r):
        l2   = erreur_L2(a, r)
        linf = erreur_Linf(a, r)
        l1   = erreur_L1(a, r)
        rm   = rmse(a, r)
        bi   = biais(a, r)
        coul = c.green if l2 < 5. else (c.yellow if l2 < 15. else c.red)
        print(f"{c.white}{label:<20s}{c.reset} | "
              f"{coul}L2={l2:5.2f}%{c.reset} | "
              f"{coul}Linf={linf:5.2f}%{c.reset} | "
              f"{coul}L1={l1:5.2f}%{c.reset} | "
              f"RMSE={rm:.3e} | "
              f"Biais={bi:+.3e}")
        return l2, linf, l1, rm, bi

    @staticmethod
    def pied_de_page(n_params):
        Rapport.separateur()
        print(f"{c.bold}{c.cyan}Fin — {n_params} parametres testes{c.reset}\n")

# ============================================================
# CLASSE DEBUG
# ============================================================

class Debug:

    @staticmethod
    def entete(titre):
        print(c.yellow + '~' * 80 + c.reset)
        print(c.bold + c.yellow + f'[DEBUG] {titre}'.center(80) + c.reset)
        print(c.yellow + '~' * 80 + c.reset)

    @staticmethod
    def fichiers(path_maillage, path_ref, path_md_list):
        Debug.entete('VERIFICATION FICHIERS')
        for label, path in [('Maillage', path_maillage), ('Reference', path_ref)]:
            exist  = os.path.isfile(path)
            coul   = c.green if exist else c.red
            statut = 'OK' if exist else 'MANQUANT'
            print(f"  {label:<12s} : {coul}{statut}{c.reset} — {path}")
        for i, path in enumerate(path_md_list):
            exist  = os.path.isfile(path)
            coul   = c.green if exist else c.red
            statut = 'OK' if exist else 'MANQUANT'
            print(f"  MD [{i}]{'':<7s} : {coul}{statut}{c.reset} — {path}")

    @staticmethod
    def maillage(MA):
        Debug.entete('MAILLAGE')
        coords = np.array(MA.getCoordinates().getValues()).reshape(-1, 3)
        print(f"  Nb noeuds  : {coords.shape[0]}")
        print(f"  X : [{coords[:,0].min():.4e}, {coords[:,0].max():.4e}]")
        print(f"  Y : [{coords[:,1].min():.4e}, {coords[:,1].max():.4e}]")
        print(f"  Z : [{coords[:,2].min():.4e}, {coords[:,2].max():.4e}]")
        print(f"  Groupes noeuds  : {MA.getGroupsOfNodes()}")
        print(f"  Groupes mailles : {MA.getGroupsOfCells()}")
        return coords

    @staticmethod
    def acces_parametres(resu, label):
        Debug.entete(f'ACCES PARAMETRES — {label}')
        params = resu.getAccessParameters()
        print(f"  Cles disponibles : {list(params.keys())}")
        print(f"  NUME_ORDRE       : {params.get('NUME_ORDRE', [])}")
        print(f"  INST             : {params.get('INST', [])}")

    @staticmethod
    def champ(sig, dep, label):
        Debug.entete(f'CHAMP — {label}')
        vm = von_mises(sig)
        print(f"  sig shape : {sig.shape}  — attendu (N, 6)")
        print(f"  dep shape : {dep.shape}  — attendu (N, 3)")
        print(f"  sig range : [{sig.min():.4e}, {sig.max():.4e}] Pa")
        print(f"  dep range : [{dep.min():.4e}, {dep.max():.4e}] m")
        print(f"  VM  range : [{vm.min():.4e}, {vm.max():.4e}] Pa")
        print(f"  VM  max au noeud : {int(np.argmax(vm))}")

    @staticmethod
    def coherence(sig_ref, sig_md, dep_ref, dep_md):
        Debug.entete('COHERENCE REF vs MD')
        ok = True
        for label, a, b in [('sig', sig_ref, sig_md), ('dep', dep_ref, dep_md)]:
            if a.shape != b.shape:
                print(c.red + f"  ERREUR {label} : {a.shape} vs {b.shape}" + c.reset)
                ok = False
            else:
                print(c.green + f"  {label} shape OK : {a.shape}" + c.reset)
        if not ok:
            print(c.red + "  ATTENTION : maillages differents — PROJ_CHAMP necessaire !" + c.reset)
        return ok

    @staticmethod
    def noeud(idx, coords, dep_ref, dep_md, sig_ref, sig_md, vm_ref, vm_md):
        Debug.entete(f'NOEUD {idx}')
        print(f"  Coords : X={coords[idx,0]:.4e}  Y={coords[idx,1]:.4e}  Z={coords[idx,2]:.4e}")
        Rapport.separateur()
        print(f"  {'Comp':<10s} | {'REF':>12s} | {'MD':>12s} | {'Ecart abs':>12s}")
        Rapport.separateur()
        for j, comp in enumerate(['DX', 'DY', 'DZ']):
            vr  = dep_ref[idx, j]
            vm_ = dep_md[idx, j]
            ec  = abs(vm_ - vr)
            coul = c.green if ec < 1e-8 else (c.yellow if ec < 1e-5 else c.red)
            print(f"  {comp:<10s} | {vr:>12.4e} | {vm_:>12.4e} | {coul}{ec:>12.4e}{c.reset}")
        for i, comp in enumerate(['SIXX', 'SIYY', 'SIZZ', 'SIXY', 'SIXZ', 'SIYZ']):
            vr  = sig_ref[idx, i]
            vm_ = sig_md[idx, i]
            ec  = abs(vm_ - vr)
            print(f"  {comp:<10s} | {vr:>12.4e} | {vm_:>12.4e} | {ec:>12.4e}")
        print(f"  {'Von Mises':<10s} | {vm_ref[idx]:>12.4e} | {vm_md[idx]:>12.4e} | "
              f"{abs(vm_md[idx]-vm_ref[idx]):>12.4e}")

# ============================================================
# EXPORT
# ============================================================

def init_export(out_dir):
    """Initialise les fichiers d'export — à appeler avant la boucle."""
    os.makedirs(out_dir, exist_ok=True)
    txt_path = os.path.join(out_dir, 'resume_erreurs.txt')
    csv_path = os.path.join(out_dir, 'resume_erreurs.csv')
    with open(txt_path, 'w') as f:
        f.write('=' * 80 + '\n')
        f.write('COMPARAISON MACRO-DEPOT vs REFERENCE\n')
        f.write('=' * 80 + '\n\n')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['parametre', 'grandeur', 'L2_pct', 'Linf_pct', 'L1_pct', 'RMSE', 'biais'])
    return txt_path, csv_path

def ecrire_export(txt_path, csv_path, valeur_param, grandeurs):
    """Ecrit les résultats d'une itération dans les fichiers."""
    with open(txt_path, 'a') as f:
        f.write(f"Parametre : {valeur_param}\n")
        f.write('-' * 80 + '\n')
        for label, (a, r) in grandeurs.items():
            l2, linf, l1, rm, bi = Rapport.ligne(label, a, r)
            f.write(f"{label:<20s} | L2={l2:5.2f}% | Linf={linf:5.2f}% | "
                    f"L1={l1:5.2f}% | RMSE={rm:.3e} | Biais={bi:+.3e}\n")
        f.write('\n')
    with open(csv_path, 'a', newline='') as f:
        writer = csv.writer(f)
        for label, (a, r) in grandeurs.items():
            writer.writerow([
                valeur_param, label,
                f"{erreur_L2(a,r):.4f}",
                f"{erreur_Linf(a,r):.4f}",
                f"{erreur_L1(a,r):.4f}",
                f"{rmse(a,r):.6e}",
                f"{biais(a,r):+.6e}",
            ])
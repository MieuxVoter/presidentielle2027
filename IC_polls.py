import pandas as pd
import os


def compute_CI(intentions, echantillon, z=1.96):
    """
    Calcule l'intervalle de confiance pour une Series de comptes bruts.

    Args:
        intentions (int): Comptes bruts d'intentions.
        echantillon (int ou pd.Series): Taille totale de l'échantillon (ou Series si variable).
        z (float): Valeur critique pour le niveau de confiance.

    Returns:
        tuple: (lower_bound, upper_bound) comme pd.Series.
    """
    p = intentions / echantillon
    se = (p * (1 - p) / echantillon) ** 0.5
    margin_of_error = z * se
    lower_bound = (p - margin_of_error).clip(lower=0)
    upper_bound = (p + margin_of_error).clip(upper=1)
    return round(lower_bound.values[0], 3), round(upper_bound.values[0], 3)


dossier = "polls"

identifiants_sondages = []

# Parcours tous les fichiers dans le répertoire
for fichier in os.listdir(dossier):
    if fichier.endswith(".csv"):
        # Extraire le nom complet sans l'extension
        identifiant = fichier[:-4]
        identifiants_sondages.append(identifiant)


polls_df = pd.read_csv("polls.csv")
poll_ids = polls_df["poll_id"].tolist()

resultats_sous_echantillons = {}

colonnes_echantillon = ["sous_echantillon3", "sous_echantillon2", "sous_echantillon1"]

for id in poll_ids:
    try:
        poll_df = pd.read_csv(f"polls/{id}.csv")
        intentions = poll_df["intentions"]
    except FileNotFoundError:
        continue

    try:
        for colonne in colonnes_echantillon:
            if (
                not polls_df[polls_df["poll_id"] == id][colonne].empty
                and not polls_df[polls_df["poll_id"] == id][colonne].isna().all()
            ):
                echantillon = polls_df[polls_df["poll_id"] == id][colonne]
                break
            else:
                continue
    except KeyError:
        continue
    try:
        erreur_inf = []
        erreur_sup = []
        for intention in intentions:
            lower_bound, upper_bound = compute_CI(intention, echantillon)
            erreur_inf.append(lower_bound)
            erreur_sup.append(upper_bound)
        poll_df["erreur_inf"] = erreur_inf
        poll_df["erreur_sup"] = erreur_sup
        poll_df.to_csv(f"polls/{id}.csv", index=False)
    except Exception as e:
        print(f"Erreur pour le sondage {id} : {e}")

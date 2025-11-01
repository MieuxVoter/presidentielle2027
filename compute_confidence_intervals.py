import os

import numpy as np
import pandas as pd
from scipy.stats import norm

FOLDER = "polls"
POLL_CSV = "polls.csv"
SAMPLE_COLS = ["sous_echantillon3", "sous_echantillon2", "sous_echantillon1"]


def compute_confidence_intervals(intentions, sample, z=1.96):
    """
    Calcule l'intervalle de confiance pour une Series de comptes bruts.

    Args:
        intentions (int): Comptes bruts d'intentions.
        sample (int): Taille totale de l'échantillon.
        z (float): Valeur critique pour le niveau de confiance.

    Returns:
        tuple: (lower_bound, upper_bound) comme pd.Series.
    """

    proportion = intentions / 100
    se = (proportion * (1 - proportion) / sample) ** 0.5
    margin_of_error = z * se
    # lower_bound = proportion - margin_of_error
    # upper_bound = proportion + margin_of_error
    # return round(lower_bound.values[0] * 100, 2), round(upper_bound.values[0] * 100, 2)
    return (np.round(-margin_of_error * 100, 2) if proportion > margin_of_error else proportion), np.round(
        margin_of_error * 100, 2
    )

def compute_p_value(intentions, sample, p0=0.5):
    """Compute the p-value for a given proportion and sample size."""
    proportion = intentions / 100
    se = np.sqrt(p0 * (1 - p0) / sample)
    z = (proportion - p0) / se
    return round(2 * (1 - norm.cdf(abs(z))), 3)

def get_poll_ids():
    """Get all ids within the poll Folder"""
    poll_ids = []
    for file in os.listdir(FOLDER):
        if file.endswith(".csv"):
            id = file[:-4]
            poll_ids.append(id)

    return poll_ids


polls_df = pd.read_csv(POLL_CSV)
poll_ids = polls_df["poll_id"].tolist()

for id in poll_ids:
    sub_df = polls_df[polls_df["poll_id"] == id]
    try:
        poll_df = pd.read_csv(f"{FOLDER}/{id}.csv")
        intentions = poll_df["intentions"]
    except FileNotFoundError:
        continue

    try:
        for col in SAMPLE_COLS:

            has_no_empty_col = not sub_df[col].empty
            has_no_nan_everywhere = not sub_df[col].isna().all()
            if has_no_empty_col and has_no_nan_everywhere:
                sample = sub_df[col].values[0]
                break
            else:
                continue
    except KeyError:
        continue

    try:
        erreur_inf = []
        erreur_sup = []
        p_values = []
        for intention in intentions:
            lower_bound, upper_bound = compute_confidence_intervals(intention, sample)
            erreur_inf.append(lower_bound)
            erreur_sup.append(upper_bound)
            p_value = compute_p_value(intention, sample)
            p_values.append(p_value)
        poll_df["erreur_inf"] = erreur_inf
        poll_df["erreur_sup"] = erreur_sup
        poll_df["p_value"] = p_values
        poll_df["significant"] = poll_df["p_value"] < 0.05
        poll_df.to_csv(f"{FOLDER}/{id}.csv", index=False)
    except Exception as e:
        print(f"Erreur pour le sondage {id} : {e}")

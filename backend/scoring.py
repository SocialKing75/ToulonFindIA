"""
Calcul du score d'opportunité d'un bien immobilier.
Compare le prix au m² du bien à la médiane DVF du quartier.
"""


MALUS_TRAVAUX = {
    "investissement": 0.0,   # travaux = opportunité de négociation
    "rp":             0.3,   # travaux = contrainte pour une famille
    "rs":             0.15,
    "mixte":          0.1,
}


def score_opportunite(bien: dict, mediane_quartier: float, profil: str, vision_result: dict | None = None) -> dict:
    """
    Calcule le score d'opportunité d'un bien.

    Args:
        bien: dict avec au moins 'prix' et 'surface'
        mediane_quartier: médiane DVF du quartier (€/m²)
        profil: "rp" | "rs" | "investissement" | "mixte"
        vision_result: résultat optionnel de l'analyse photo (bonus)

    Returns:
        dict avec 'score', 'ecart_pct', 'label'
    """
    prix_m2 = bien["prix"] / bien["surface"]
    ecart_pct = (prix_m2 - mediane_quartier) / mediane_quartier * 100
    score = -ecart_pct

    if vision_result and "travaux_detectes" in vision_result and vision_result["travaux_detectes"]:
        malus = MALUS_TRAVAUX.get(profil, 0.1)
        score *= (1 - malus)

    if ecart_pct < -10:
        label = "Sous-évalué 🟢"
    elif ecart_pct < 5:
        label = "Dans la norme 🟡"
    else:
        label = "Surévalué 🔴"

    return {
        "score": round(score, 2),
        "ecart_pct": round(ecart_pct, 1),
        "label": label,
        "prix_m2": round(prix_m2, 0),
    }


def fiche_decision(bien: dict, dvf_quartier: dict) -> str:
    """
    Génère la fiche structurée transmise au LLM.

    Returns:
        Texte structuré : prix vs médiane, écart %, conseil de négociation
    """
    prix_m2 = bien["prix"] / bien["surface"]
    mediane = dvf_quartier.get("mediane_prix_m2", prix_m2)
    ecart_pct = (prix_m2 - mediane) / mediane * 100

    fiche = f"""Type: {bien.get('type', 'N/A')} — {bien.get('surface', '?')}m² — {bien.get('quartier', '?')}
Prix affiché: {bien.get('prix', '?')}€ ({prix_m2:.0f}€/m²)
Médiane DVF: {mediane:.0f}€/m²
Écart: {ecart_pct:+.1f}%"""
    return fiche


def rendement_locatif(bien: dict, loyer_estime: float) -> dict:
    """
    Calcule le rendement brut et net estimé (bonus investissement).

    Args:
        bien: dict avec 'prix'
        loyer_estime: loyer mensuel estimé en €

    Returns:
        dict avec 'rendement_brut_pct', 'rendement_net_pct'
    """
    loyer_annuel = loyer_estime * 12
    rendement_brut = (loyer_annuel / bien["prix"]) * 100
    rendement_net = rendement_brut * 0.8
    return {
        "rendement_brut_pct": round(rendement_brut, 2),
        "rendement_net_pct": round(rendement_net, 2),
    }

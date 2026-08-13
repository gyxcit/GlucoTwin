"""Sensibilite du modele a l'incertitude sur le RER (VCO2 non mesure)."""
from glucotwin.metabolic_engine import load_activities, vo2_from_met, rer_from_met, frayn_oxidation

acts = load_activities()
W, D = 78.0, 30.0
DELTA = 0.05  # incertitude plausible sur le RER estime

print(f"Impact d'une erreur de +/- {DELTA} sur le RER  (sujet {W:.0f} kg, {D:.0f} min)")
print("=" * 86)
print(f"{'Activite':<30} {'RER':>6} {'Glucides g':>12} {'variation':>12} {'Energie kcal':>14} {'variation':>11}")
print("-" * 86)

for code in ["MAR03", "MAR04", "VEL03", "CRS02", "FIT05"]:
    a = acts[code]
    vo2 = vo2_from_met(a.met, W)
    base_rer = rer_from_met(a.met)
    rows = []
    for label, rer in [("bas", base_rer - DELTA), ("estime", base_rer), ("haut", base_rer + DELTA)]:
        rer = max(0.71, min(1.0, rer))
        cho, fat = frayn_oxidation(vo2, rer * vo2)
        cho_g, fat_g = cho * D, fat * D
        rows.append((label, rer, cho_g, cho_g * 4 + fat_g * 9))
    _, _, cho_ref, kcal_ref = rows[1]
    for label, rer, cho_g, kcal in rows:
        dc = (cho_g - cho_ref) / cho_ref * 100
        dk = (kcal - kcal_ref) / kcal_ref * 100
        name = a.label[:29] if label == "estime" else ""
        print(f"{name:<30} {rer:>6.3f} {cho_g:>12.1f} {dc:>+11.1f}% {kcal:>14.1f} {dk:>+10.1f}%")
    print("-" * 86)

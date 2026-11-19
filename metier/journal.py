"""Journal des modifications : qui, quand, quoi, ancienne et nouvelle valeur."""

from metier.dates import horodatage


def differences(avant, apres, champs):
    """{champ: (ancienne, nouvelle)} pour les champs modifiés."""
    return {
        c: (str(avant.get(c, "") or ""), str(apres.get(c, "") or ""))
        for c in champs
        if str(avant.get(c, "") or "") != str(apres.get(c, "") or "")
    }


def tracer(stockage, utilisateur, onglet, identifiant, changements):
    if not changements:
        return
    quand = horodatage()
    stockage.ajouter_lignes("Journal", [
        {"horodatage": quand, "utilisateur": utilisateur, "onglet": onglet, "id": identifiant,
         "champ": champ, "ancienne": anc, "nouvelle": nouv}
        for champ, (anc, nouv) in changements.items()
    ])


def historique(stockage, onglet, identifiant, limite=30):
    lignes = [l for l in stockage.lire("Journal")
              if l.get("onglet") == onglet and l.get("id") == identifiant]
    return list(reversed(lignes))[:limite]

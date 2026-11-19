"""Outils communs aux routes."""

from functools import wraps

from flask import abort, current_app, g

from metier.droits import peut_voir


def stockage():
    return current_app.extensions["stockage"]


def nom_utilisateur():
    return (g.compte or {}).get("nom", "?")


def onglet_requis(cle_onglet):
    """Refuse l'accès (403) si l'onglet n'est pas visible pour les rôles du compte."""

    def decorateur(vue):
        @wraps(vue)
        def enveloppe(*args, **kwargs):
            if not peut_voir(g.compte, cle_onglet):
                abort(403)
            return vue(*args, **kwargs)

        return enveloppe

    return decorateur

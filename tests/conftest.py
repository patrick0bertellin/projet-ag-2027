"""Fixtures : application sur un stockage en mémoire, données de la v05, un compte par rôle."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from metier.comptes import creer  # noqa: E402
from metier.import_json import importer  # noqa: E402
from stockage.memoire import StockageMemoire  # noqa: E402

MDP = "motdepasse-test"

COMPTES = {
    "chef": ("Patrick Test", "patrick@test.fr", ["chef_projet"], "Patrick", ""),
    "com": ("Siham Test", "siham@test.fr", ["communication"], "Siham", ""),
    "budget": ("Louis Test", "louis@test.fr", ["budget"], "Louis", ""),
    "contrib": ("Resp Pôle", "pole@test.fr", ["contribution"], "", "Pôle 1"),
    "lecture": ("Pierre Test", "pierre@test.fr", ["lecture"], "Pierre", ""),
}


_MODELE = None


def _stockage_modele():
    """Construit une seule fois (le hachage des mots de passe est volontairement lent)."""
    global _MODELE
    if _MODELE is None:
        _MODELE = StockageMemoire()
        importer(_MODELE)
        for nom, courriel, roles, alias, pole in COMPTES.values():
            creer(_MODELE, courriel.split("@")[0], nom, roles, MDP, courriel=courriel, alias=alias,
                  pole=pole, doit_changer=False)
    return _MODELE


@pytest.fixture
def stockage():
    st = StockageMemoire()
    st.donnees = copy.deepcopy(_stockage_modele().donnees)
    return st


@pytest.fixture
def app(stockage):
    application = create_app({"TESTING": True, "SECRET_KEY": "test", "VERIFIER_CSRF": False}, stockage=stockage)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def connecter(client, qui):
    identifiant = COMPTES[qui][1].split("@")[0]
    return client.post("/connexion", data={"identifiant": identifiant, "mot_de_passe": MDP})


@pytest.fixture
def connexion(client):
    def _connecter(qui):
        connecter(client, qui)
        return client

    return _connecter

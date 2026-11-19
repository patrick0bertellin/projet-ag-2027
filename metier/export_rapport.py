"""Export Word du rapport d'activité 2026 — perspectives 2027, compilé à partir des fiches des pôles.

Base : donnees/modele_rapport.docx (couverture et mise en page du rapport 2025, corps vidé). On réutilise ses
styles nommés : Heading 1 (titres de partie), Style5 (Bilan / Perspectives, rouge), Style4 (rubriques),
Body Text, liste pat (puces), Table Grid. Les parties vides sont marquées « [à compléter] » surligné en jaune ;
une fiche non validée est signalée en tête de sa partie.
"""

import io
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from metier.rapport import GENERAL, VALIDEE, lire_fiches, lire_vue

MODELE = Path(__file__).resolve().parent.parent / "donnees" / "modele_rapport.docx"
A_COMPLETER = "[à compléter]"
INTRO_CHIFFRES = (
    "Le Comité Départemental Olympique et Sportif des Yvelines (CDOS 78) rassemble et coordonne le mouvement sportif "
    "yvelinois. Il fédère les comités départementaux adhérents et agit pour l'ensemble des organismes comme force de "
    "proposition, d'expertise et de prospective auprès des acteurs publics et privés du sport dans le département."
)
CONCLUSION = (
    "Le CDOS 78 entend ainsi confirmer son rôle d'acteur incontournable et de référence dans l'écosystème sportif "
    "yvelinois, au bénéfice des clubs et des licenciés du département."
)
PUCES = ("- ", "• ", "* ", "– ")


class Redacteur:
    def __init__(self, document):
        self.d = document

    def titre(self, texte):
        p = self.d.add_paragraph(texte, style="Heading 1")
        p.paragraph_format.page_break_before = True

    def sous_titre(self, texte):
        self.d.add_paragraph(texte, style="Style5")

    def rubrique(self, texte):
        self.d.add_paragraph(texte, style="Style4")

    def texte(self, contenu):
        self.d.add_paragraph(contenu, style="Body Text")

    def manque(self, style="Body Text"):
        p = self.d.add_paragraph(style=style)
        p.add_run(A_COMPLETER).font.highlight_color = WD_COLOR_INDEX.YELLOW

    def alerte(self, contenu):
        p = self.d.add_paragraph(style="Body Text")
        r = p.add_run("▶ " + contenu)
        r.italic = True
        r.font.highlight_color = WD_COLOR_INDEX.YELLOW

    def bloc(self, contenu, puces=False):
        """Texte saisi : une ligne = un paragraphe ; « - » ou « • » en début de ligne (ou puces=True) = puce."""
        lignes = [l.strip() for l in (contenu or "").splitlines() if l.strip()]
        if not lignes:
            self.manque("liste pat" if puces else "Body Text")
            return
        for ligne in lignes:
            marque = ligne.startswith(PUCES)
            if marque:
                ligne = ligne[2:].strip()
            self.d.add_paragraph(ligne, style="liste pat" if (puces or marque) else "Body Text")

    def tableau(self, entetes, lignes, largeurs):
        """« Grille du tableau » à la charte CDOS 78 : en-tête #0070C0 blanc gras centré, lignes alternées #D9D9D9."""
        t = self.d.add_table(rows=1, cols=len(entetes), style="Table Grid")
        for i, e in enumerate(entetes):
            c = t.rows[0].cells[i]
            r = c.paragraphs[0].add_run(e)
            r.bold, r.font.color.rgb, r.font.size = True, RGBColor(0xFF, 0xFF, 0xFF), Pt(9)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            _ombrer(c, "0070C0")
        for n, ligne in enumerate(lignes):
            cellules = t.add_row().cells
            for i, valeur in enumerate(ligne):
                r = cellules[i].paragraphs[0].add_run(valeur or "")
                r.font.size = Pt(9)
                if n % 2 == 1:
                    _ombrer(cellules[i], "D9D9D9")
        entete = OxmlElement("w:tblHeader")
        entete.set(qn("w:val"), "true")
        t.rows[0]._tr.get_or_add_trPr().append(entete)
        t.autofit = False
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, col in enumerate(t._tbl.tblGrid.findall(qn("w:gridCol"))):
            col.set(qn("w:w"), str(int(Cm(largeurs[i]).twips)))
        for ligne in t.rows:
            for i, largeur in enumerate(largeurs):
                ligne.cells[i].width = Cm(largeur)
                for par in ligne.cells[i].paragraphs:
                    par.paragraph_format.space_before = par.paragraph_format.space_after = Pt(1)
                    if ligne._index > 0:
                        par.alignment = WD_ALIGN_PARAGRAPH.LEFT
        self.d.add_paragraph(style="Body Text")

    def signatures(self):
        t = self.d.add_table(rows=1, cols=3, style="Table Grid")
        for i, (nom, fonction) in enumerate([("Pierre TREGUIER", "Président"), ("", ""),
                                             ("Patrick BERTELLIN", "Secrétaire Général")]):
            c = t.rows[0].cells[i]
            if nom:
                c.paragraphs[0].add_run(nom).bold = True
                c.add_paragraph(fonction)
        bordures = OxmlElement("w:tblBorders")
        for cote in ("top", "left", "bottom", "right", "insideH", "insideV"):
            b = OxmlElement(f"w:{cote}")
            b.set(qn("w:val"), "nil")
            bordures.append(b)
        t._tbl.tblPr.append(bordures)


def _ombrer(cellule, couleur):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), couleur)
    cellule._tc.get_or_add_tcPr().append(shd)


def _engagements(r, vue, entete):
    if vue["engagements"]:
        r.tableau([entete, "État", "Commentaire"],
                  [[l["engagement"], l.get("etat") or A_COMPLETER, l.get("commentaire", "")] for l in vue["engagements"]],
                  [8.0, 2.6, 6.4])
    if vue["non_prevues"]:
        r.rubrique("Actions réalisées ou engagées en 2026 non prévues")
        r.tableau(["Action non prévue", "État", "Commentaire"],
                  [[l["engagement"], l.get("etat", ""), l.get("commentaire", "")] for l in vue["non_prevues"]],
                  [8.0, 2.6, 6.4])


def _chiffres(r, vue):
    r.tableau(["Indicateur", "2025 (rappel)", "2026", "Source"],
              [[l["indicateur"], l.get("valeur_reference", ""), l.get("valeur_annee") or A_COMPLETER,
                l.get("source", "")] for l in vue["indicateurs"]],
              [7.0, 2.8, 2.6, 4.6])


def _statut(r, fiche):
    if fiche.get("statut") != VALIDEE:
        r.alerte(f"Fiche « {fiche.get('statut')} » : contenu non encore validé par le Chef de projet.")


def _general(r, vue):
    fiche = vue["fiche"]
    r.titre(fiche.get("titre") or "INTRODUCTION")
    _statut(r, fiche)
    r.bloc(fiche.get("bilan"))
    if vue["engagements"] or vue["non_prevues"]:
        r.rubrique("Bilan des caps annoncés pour 2026")
        _engagements(r, vue, "Cap annoncé pour 2026")
    r.titre("LE CDOS 78 EN CHIFFRES")
    r.texte(INTRO_CHIFFRES)
    if vue["indicateurs"]:
        _chiffres(r, vue)


def _pole(r, vue):
    fiche = vue["fiche"]
    r.titre(fiche.get("titre") or fiche["pole"].upper())
    _statut(r, fiche)
    if fiche.get("commission"):
        r.texte("Commission animée par : " + fiche["commission"])
    r.rubrique("Présentation du pôle")
    r.bloc(fiche.get("presentation"))
    r.sous_titre("Bilan 2026")
    if vue["engagements"] or vue["non_prevues"]:
        r.rubrique("Bilan des engagements annoncés pour 2026")
        _engagements(r, vue, "Engagement annoncé dans le rapport 2025")
    if vue["indicateurs"]:
        r.rubrique("Chiffres clés 2026")
        _chiffres(r, vue)
    r.rubrique("Actions menées en 2026")
    r.bloc(fiche.get("bilan"))
    r.sous_titre("Perspectives 2027")
    r.bloc(fiche.get("perspectives"), puces=True)


def exporter_rapport(stockage, modele=MODELE):
    document = docx.Document(str(modele))
    r = Redacteur(document)
    vues = {f["pole"]: lire_vue(stockage, f["pole"]) for f in lire_fiches(stockage)}
    general = vues.pop(GENERAL, None)
    if general:
        _general(r, general)
    for vue in vues.values():
        _pole(r, vue)
    r.titre("PERSPECTIVES GÉNÉRALES 2027")
    if general:
        r.bloc(general["fiche"].get("perspectives"))
    else:
        r.manque()
    r.texte(CONCLUSION)
    r.signatures()
    sortie = io.BytesIO()
    document.save(sortie)
    return sortie.getvalue()

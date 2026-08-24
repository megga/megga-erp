import base64
from datetime import datetime, time

import pytz

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..om_parser import (
    decode_text,
    norm,
    parse_swiss_amount,
    parse_swiss_date,
    parse_swiss_time,
    parse_table,
    slug,
)

# Espace des identifiants externes de la reprise. Le double soulignement
# garantit qu'aucun module installable ne portera jamais ce nom : une
# désinstallation ne peut donc pas emporter les fiches importées.
NS = '__megga_om__'

# En-têtes acceptés, par champ logique — déjà passés par norm(). Un
# export Office Maker renomme librement ses colonnes : on rapproche par
# alias plutôt que d'exiger un gabarit.
ALIAS = {
    'ref': ('ref', 'reference', 'n', 'no', 'numero', 'id', 'code'),
    'name': ('nom', 'nom complet', 'client', 'nom client', 'societe'),
    'first_name': ('prenom',),
    'email': ('email', 'e mail', 'courriel', 'mail'),
    'phone': ('telephone', 'tel', 'phone', 'portable', 'mobile', 'natel'),
    'street': ('rue', 'adresse'),
    'zip': ('npa', 'cp', 'code postal'),
    'city': ('localite', 'ville', 'lieu'),
    'country': ('pays', 'country'),
    'patient_ref': ('client', 'patient', 'ref client', 'no client',
                    'numero client'),
    'kind': ('type', 'type de mandat'),
    'date_start': ('debut', 'date debut', 'du', 'date'),
    'date_end': ('fin', 'date fin', 'au'),
    'fee': ('honoraires', 'forfait', 'honoraires forfait'),
    'state': ('etat', 'statut', 'status'),
    'mandate_ref': ('mandat', 'ref mandat', 'no mandat', 'numero mandat'),
    'date': ('date', 'jour'),
    'time': ('heure', 'h'),
    'label': ('libelle', 'description', 'designation', 'evenement',
              'prestation'),
    'service': ('type', 'type de prestation', 'categorie',
                'code prestation'),
    'provider': ('prestataire', 'fournisseur', 'medecin', 'praticien'),
    'price': ('prix', 'prix client', 'montant', 'facture client'),
    'cost': ('cout', 'cout reel', 'prix coutant', 'achat'),
    'duration': ('duree', 'duree h'),
}

MANDATE_KINDS = {
    'hospitalise': 'hospitalise', 'hospitalisation': 'hospitalise',
    'stationnaire': 'hospitalise',
    'ambulatoire': 'ambulatoire', 'check up': 'ambulatoire',
    'checkup': 'ambulatoire',
}
# L'historique arrive clôturé par défaut : la reprise décrit du passé.
MANDATE_STATES = {
    'offre': 'draft', 'devis': 'draft',
    'en cours': 'confirmed', 'ouvert': 'confirmed', 'actif': 'confirmed',
    'cloture': 'done', 'termine': 'done', 'ferme': 'done',
    'annule': 'cancelled',
}


class MeggaCareImport(models.TransientModel):
    """L'assistant de reprise : un fichier, un type de fiches, un
    rapport. Idempotent par référence externe — ré-importer met à jour,
    jamais ne duplique — et strict sur le contenu : toute ligne
    illisible est rejetée avec sa raison, jamais devinée. L'ordre
    d'import suit les liaisons : clients, prestataires, mandats, puis
    événements."""
    _name = 'megga.care.import'
    _description = "Reprise Office Maker"

    kind = fields.Selection([
        ('patients', "Clients (patients)"),
        ('providers', "Prestataires"),
        ('mandates', "Mandats"),
        ('events', "Événements de mandat"),
    ], string="Fiches", required=True, default='patients')
    file_data = fields.Binary("Export Office Maker", required=True)
    filename = fields.Char("Nom du fichier")
    encoding = fields.Selection([
        ('auto', "Détection automatique"),
        ('utf-8', "UTF-8"),
        ('utf-16', "UTF-16"),
        ('cp1252', "Windows (cp1252)"),
        ('mac_roman', "Mac Roman"),
    ], string="Encodage", required=True, default='auto')
    delimiter = fields.Selection([
        ('auto', "Détection automatique"),
        ('tab', "Tabulation"),
        (';', "Point-virgule"),
        (',', "Virgule"),
    ], string="Séparateur", required=True, default='auto')
    state = fields.Selection([
        ('draft', "À importer"),
        ('done', "Importé"),
    ], default='draft', required=True)
    result = fields.Text("Rapport", readonly=True)

    # ------------------------------------------------------------------
    # Point d'entrée
    # ------------------------------------------------------------------

    def action_import(self):
        self.ensure_one()
        raw = base64.b64decode(self.file_data)
        try:
            text = decode_text(raw, self.encoding)
        except (UnicodeDecodeError, LookupError):
            raise UserError(_(
                "Le fichier ne se décode pas en %s : essayez un autre"
                " encodage.") % self.encoding)
        headers, rows = parse_table(text, self.delimiter)
        if not rows:
            raise UserError(_(
                "Aucune ligne de données : la première ligne doit porter"
                " les en-têtes, les suivantes les fiches."))
        importer = getattr(self, '_import_%s' % self.kind)
        created, updated, rejected, notes = importer(rows)
        self.write({
            'state': 'done',
            'result': self._report(
                len(rows), created, updated, rejected, notes),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _report(self, total, created, updated, rejected, notes):
        lines = [_(
            "%(total)s ligne(s) lue(s) : %(crees)s créée(s),"
            " %(maj)s mise(s) à jour, %(rejets)s rejetée(s).",
            total=total, crees=created, maj=updated,
            rejets=len(rejected))]
        for line_no, reason in rejected:
            lines.append(_("  ligne %(ligne)s : %(raison)s",
                           ligne=line_no, raison=reason))
        lines.extend("  %s" % note for note in notes)
        if rejected:
            lines.append(_(
                "Corrigez la source (ou le référentiel) puis relancez le"
                " même fichier : l'import met à jour, il ne duplique"
                " jamais."))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Références externes (idempotence)
    # ------------------------------------------------------------------

    @staticmethod
    def _xmlid_name(prefix, ref):
        propre = slug(ref).replace('-', '_') or 'sans_ref'
        return '%s_%s' % (prefix, propre)

    def _resolve(self, prefix, ref):
        return self.env.ref(
            '%s.%s' % (NS, self._xmlid_name(prefix, ref)),
            raise_if_not_found=False)

    def _bind(self, record, prefix, ref):
        self.env['ir.model.data']._update_xmlids([{
            'xml_id': '%s.%s' % (NS, self._xmlid_name(prefix, ref)),
            'record': record,
            'noupdate': False,
        }])

    # ------------------------------------------------------------------
    # Aides communes
    # ------------------------------------------------------------------

    @staticmethod
    def _get(row, field):
        for alias in ALIAS[field]:
            if alias in row and row[alias]:
                return row[alias]
        return ''

    def _country(self, value, notes, line_no):
        """Pays par code ISO2 puis par nom ; introuvable -> champ sauté
        avec avertissement, jamais un rejet (une adresse incomplète ne
        condamne pas la fiche)."""
        if not value:
            return None
        Country = self.env['res.country']
        pays = None
        if len(value) == 2:
            pays = Country.search([('code', '=', value.upper())], limit=1)
        if not pays:
            pays = Country.search([('name', '=ilike', value)], limit=1)
        if not pays:
            notes.append(_(
                "ligne %(ligne)s : pays %(pays)r inconnu, champ ignoré",
                ligne=line_no, pays=value))
            return None
        return pays

    def _partner_vals(self, row, notes, line_no):
        vals = {}
        for field, key in (('email', 'email'), ('phone', 'phone'),
                           ('street', 'street'), ('zip', 'zip'),
                           ('city', 'city')):
            value = self._get(row, key)
            if value:
                vals[field] = value
        pays = self._country(self._get(row, 'country'), notes, line_no)
        if pays:
            vals['country_id'] = pays.id
        return vals

    def _full_name(self, row):
        nom = self._get(row, 'name')
        prenom = self._get(row, 'first_name')
        return ("%s %s" % (prenom, nom)).strip() if prenom else nom

    # ------------------------------------------------------------------
    # Les quatre importations
    # ------------------------------------------------------------------

    def _import_patients(self, rows):
        created = updated = 0
        rejected, notes = [], []
        for line_no, row in enumerate(rows, start=2):
            name = self._full_name(row)
            if not name:
                rejected.append((line_no, _("nom manquant")))
                continue
            ref = self._get(row, 'ref') or slug(name)
            vals = self._partner_vals(row, notes, line_no)
            patient = self._resolve('patient', ref)
            if patient:
                patient.write(dict(vals, name=name))
                updated += 1
            else:
                patient = self.env['megga.care.patient'].create(
                    dict(vals, name=name))
                self._bind(patient, 'patient', ref)
                created += 1
        return created, updated, rejected, notes

    def _import_providers(self, rows):
        created = updated = 0
        rejected, notes = [], []
        for line_no, row in enumerate(rows, start=2):
            name = self._full_name(row)
            if not name:
                rejected.append((line_no, _("nom manquant")))
                continue
            ref = self._get(row, 'ref') or slug(name)
            vals = self._partner_vals(row, notes, line_no)
            provider = self._resolve('provider', ref)
            if provider:
                provider.write(dict(vals, name=name))
                updated += 1
            else:
                provider = self.env['res.partner'].create(
                    dict(vals, name=name, supplier_rank=1))
                self._bind(provider, 'provider', ref)
                created += 1
        return created, updated, rejected, notes

    def _import_mandates(self, rows):
        created = updated = 0
        rejected, notes = [], []
        for line_no, row in enumerate(rows, start=2):
            ref = self._get(row, 'ref')
            if not ref:
                rejected.append((line_no, _("référence de mandat"
                                            " manquante")))
                continue
            patient_ref = self._get(row, 'patient_ref')
            patient = patient_ref and self._resolve('patient', patient_ref)
            if not patient:
                rejected.append((line_no, _(
                    "client %(ref)r introuvable — importez d'abord les"
                    " clients", ref=patient_ref)))
                continue
            try:
                date_start = parse_swiss_date(self._get(row, 'date_start'))
                date_end = parse_swiss_date(self._get(row, 'date_end'))
                fee = parse_swiss_amount(self._get(row, 'fee'))
            except ValueError as erreur:
                rejected.append((line_no, str(erreur)))
                continue
            vals = {'patient_id': patient.id}
            # Type et état ne s'écrivent que si la colonne parle : un
            # ré-import ne doit pas rabattre sur les défauts une
            # correction faite à la main entre deux répétitions.
            kind_raw = norm(self._get(row, 'kind'))
            if kind_raw:
                vals['kind'] = MANDATE_KINDS.get(kind_raw, 'ambulatoire')
            state_raw = norm(self._get(row, 'state'))
            if state_raw:
                vals['state'] = MANDATE_STATES.get(state_raw, 'done')
            elif not self._resolve('mandate', ref):
                # Création sans colonne d'état : l'historique repris
                # arrive clôturé.
                vals['state'] = 'done'
            if date_start:
                vals['date_start'] = date_start
            if date_end:
                vals['date_end'] = date_end
            if fee is not None:
                vals.update(fee_mode='forfait', fee_flat=fee)
            mandate = self._resolve('mandate', ref)
            if mandate:
                mandate.write(vals)
                updated += 1
            else:
                mandate = self.env['megga.care.mandate'].create(vals)
                self._bind(mandate, 'mandate', ref)
                created += 1
        return created, updated, rejected, notes

    def _import_events(self, rows):
        created = updated = 0
        rejected, notes = [], []
        tz = pytz.timezone(self.env.user.tz or 'Europe/Zurich')
        Type = self.env['megga.care.service.type']
        Partner = self.env['res.partner']
        for line_no, row in enumerate(rows, start=2):
            mandate_ref = self._get(row, 'mandate_ref')
            mandate = mandate_ref and self._resolve('mandate', mandate_ref)
            if not mandate:
                rejected.append((line_no, _(
                    "mandat %(ref)r introuvable — importez d'abord les"
                    " mandats", ref=mandate_ref)))
                continue
            label = self._get(row, 'label')
            if not label:
                rejected.append((line_no, _("libellé manquant")))
                continue
            try:
                jour = parse_swiss_date(self._get(row, 'date'))
                heure = parse_swiss_time(self._get(row, 'time'))
                price = parse_swiss_amount(self._get(row, 'price'))
                cost = parse_swiss_amount(self._get(row, 'cost'))
                duration = parse_swiss_amount(self._get(row, 'duration'))
            except ValueError as erreur:
                rejected.append((line_no, str(erreur)))
                continue
            if not jour:
                rejected.append((line_no, _("date manquante")))
                continue
            service_raw = self._get(row, 'service')
            service = Type.search(
                [('code', '=', service_raw.upper())], limit=1) or Type.search(
                [('name', '=ilike', service_raw)], limit=1)
            if not service:
                rejected.append((line_no, _(
                    "type de prestation %(type)r inconnu — complétez le"
                    " référentiel (Conciergerie > Configuration) puis"
                    " relancez", type=service_raw)))
                continue
            provider = None
            provider_name = self._get(row, 'provider')
            if provider_name:
                provider = Partner.search(
                    [('name', '=ilike', provider_name)], limit=1)
                if not provider:
                    provider = Partner.create({
                        'name': provider_name, 'supplier_rank': 1})
                    notes.append(_(
                        "ligne %(ligne)s : prestataire %(nom)r créé",
                        ligne=line_no, nom=provider_name))
            # L'agenda vit en heure locale ; la base stocke en UTC.
            local = tz.localize(
                datetime.combine(jour, heure or time(8, 0)))
            vals = {
                'mandate_id': mandate.id,
                'name': label,
                'service_type_id': service.id,
                'provider_id': provider.id if provider else False,
                'date': local.astimezone(pytz.utc).replace(tzinfo=None),
                'duration': duration or 1.0,
                'price_client': price or 0.0,
                'cost_price': cost or 0.0,
            }
            # Sans colonne « ref », la clé dérive du mandat, du jour et
            # du libellé — stable d'un export à l'autre. Deux événements
            # identiques le même jour exigent une colonne ref.
            ref = self._get(row, 'ref') or "%s-%s-%s" % (
                mandate_ref, jour.isoformat(), slug(label))
            event = self._resolve('event', ref)
            if event:
                event.write(vals)
                updated += 1
            else:
                event = self.env['megga.care.event'].create(vals)
                self._bind(event, 'event', ref)
                created += 1
        return created, updated, rejected, notes

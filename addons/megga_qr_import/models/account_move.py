import io
import logging

from odoo import Command, _, models

from ..qr_parser import parse_spc

_logger = logging.getLogger(__name__)

# La lecture des QR dans les images et les PDF exige pyzbar (libzbar) et
# un lecteur PDF ; tous deux sont OPTIONNELS. Absents, ces sources sont
# ignorées silencieusement — la charge SPC en texte reste toujours lue.
try:
    from pyzbar.pyzbar import decode as _zbar_decode
except ImportError:
    _zbar_decode = None
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None


class AccountMove(models.Model):
    """Branche la lecture de la QR-facture sur le cadre de décodage des
    pièces jointes d'account : l'e-mail reçu par l'alias du journal
    d'achat crée le brouillon, la QR le remplit. Priorité sous
    Factur-X/UBL (20) : un XML complet gagne toujours contre une QR qui
    ne porte que le volet paiement."""
    _inherit = 'account.move'

    def _get_edi_decoder(self, file_data, new=False):
        if self.move_type in ('in_invoice', 'in_refund'):
            data = self._megga_qr_extract(file_data)
            if data:
                file_data['megga_qr_data'] = data
                return {
                    'priority': 10,
                    'decoder': self.env['account.move']._megga_qr_decode,
                }
        return super()._get_edi_decoder(file_data, new=new)

    def _megga_qr_decode(self, invoice, file_data, new):
        data = file_data.get('megga_qr_data') \
            or invoice._megga_qr_extract(file_data)
        if not data:
            return _("aucune QR-facture lisible dans la pièce")
        invoice._megga_qr_apply(data)

    # ------------------------------------------------------------------
    # Extraction de la charge utile SPC
    # ------------------------------------------------------------------

    def _megga_qr_extract(self, file_data):
        """Cherche une charge SPC valide dans la pièce : texte brut,
        image, puis pages PDF. La première charge conforme gagne ; les
        malformées sont ignorées (une pièce peut porter plusieurs QR)."""
        raw = file_data.get('raw') or b''
        mimetype = file_data.get('mimetype') or ''
        for payload in self._megga_qr_payloads(raw, mimetype):
            try:
                return parse_spc(payload)
            except ValueError as erreur:
                _logger.info(
                    "QR ignoré dans %s : %s", file_data.get('name'), erreur)
        return None

    def _megga_qr_payloads(self, raw, mimetype):
        if mimetype.startswith('text/'):
            texte = raw.decode('utf-8', errors='replace')
            if texte.lstrip().startswith('SPC'):
                yield texte.lstrip()
            return
        if mimetype.startswith('image/'):
            yield from self._megga_qr_scan_image(raw)
            return
        if mimetype == 'application/pdf':
            yield from self._megga_qr_scan_pdf(raw)

    def _megga_qr_scan_image(self, raw):
        if not _zbar_decode or not Image:
            return
        try:
            image = Image.open(io.BytesIO(raw))
            for symbole in _zbar_decode(image):
                yield symbole.data.decode('utf-8', errors='replace')
        except Exception:  # noqa: BLE001 - une image illisible n'est pas une erreur
            _logger.info("image illisible pour la lecture QR", exc_info=True)

    def _megga_qr_scan_pdf(self, raw):
        """Les QR des PDF sont des IMAGES embarquées : on les extrait
        (sans rendu de page) et on les décode une à une. Un QR dessiné
        en vectoriel reste hors de portée — la pièce est alors ignorée,
        jamais devinée."""
        if not _zbar_decode or not PdfReader or not Image:
            return
        try:
            lecteur = PdfReader(io.BytesIO(raw))
            for page in lecteur.pages:
                for image_page in page.images:
                    for symbole in _zbar_decode(image_page.image):
                        yield symbole.data.decode('utf-8', errors='replace')
        except Exception:  # noqa: BLE001 - un PDF illisible n'est pas une erreur
            _logger.info("PDF illisible pour la lecture QR", exc_info=True)

    # ------------------------------------------------------------------
    # Application au brouillon
    # ------------------------------------------------------------------

    def _megga_qr_apply(self, data):
        """Remplit le brouillon depuis la charge SPC — champs VIDES
        uniquement, une saisie existante n'est jamais écrasée — puis
        raconte ce qui a été lu dans le fil de discussion."""
        self.ensure_one()
        lu = []
        banque = self.env['res.partner.bank'].search(
            [('sanitized_acc_number', '=', data['iban'])], limit=1)

        if not self.partner_id:
            partner = banque.partner_id
            if not partner:
                partner = self._megga_qr_create_partner(data['creditor'])
                lu.append(_("créancier créé : %s") % partner.display_name)
            else:
                lu.append(_("créancier reconnu par son IBAN : %s")
                          % partner.display_name)
            self.partner_id = partner

        if not banque and self.partner_id:
            banque = self.env['res.partner.bank'].create({
                'acc_number': data['iban'],
                'partner_id': self.partner_id.id,
            })
            lu.append(_("compte %s attaché au créancier") % data['iban'])
        if (not self.partner_bank_id and banque
                and banque.partner_id == self.partner_id):
            self.partner_bank_id = banque

        devise = self.env['res.currency'].search(
            [('name', '=', data['currency'])], limit=1)
        if (devise and devise != self.currency_id
                and not self.invoice_line_ids):
            self.currency_id = devise
            lu.append(_("devise %s") % devise.name)

        if not self.invoice_line_ids and data['amount']:
            libelle = data['message'] or _(
                "QR-facture — %s") % data['creditor']['name']
            self.invoice_line_ids = [Command.create({
                'name': libelle,
                'quantity': 1.0,
                'price_unit': data['amount'],
            })]
            lu.append(_("montant %(montant).2f %(devise)s",
                        montant=data['amount'], devise=data['currency']))

        if not self.payment_reference and data['reference']:
            self.payment_reference = data['reference']
            lu.append(_("référence %(type)s %(reference)s",
                        type=data['ref_type'], reference=data['reference']))

        if lu:
            self.message_post(
                body=_("QR-facture lue : %s.") % ", ".join(lu))
        else:
            self.message_post(
                body=_("QR-facture lue, rien à compléter : tous les"
                       " champs étaient déjà saisis."))

    def _megga_qr_create_partner(self, creditor):
        rue = " ".join(part for part in (
            creditor['street'], creditor['house']) if part)
        pays = self.env['res.country'].search(
            [('code', '=', creditor['country'].upper())], limit=1)
        return self.env['res.partner'].create({
            'name': creditor['name'],
            'street': rue or False,
            'zip': creditor['zip'] or False,
            'city': creditor['city'] or False,
            'country_id': pays.id or False,
        })

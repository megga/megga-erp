from odoo.tests import TransactionCase

from ..qr_parser import mod10r, parse_spc, qrr_valid, scor_valid

# Les exemples officiels des Swiss Implementation Guidelines QR-bill :
# QR-IBAN (IID 31999) avec référence QRR, IBAN ordinaire pour SCOR/NON.
QR_IBAN = 'CH4431999123000889012'
IBAN = 'CH5800791123000889012'
QRR = '210000000003139471430009017'
SCOR = 'RF18539007547034'


def payload(**overrides):
    """Une charge SPC 0200 valide (créancier structuré, débiteur, QRR),
    dont chaque ligne peut être surchargée par son index."""
    lines = [
        'SPC', '0200', '1', QR_IBAN,
        'S', 'Max Muster & Söhne', 'Musterstrasse', '123',
        '8000', 'Seldwyla', 'CH',
        '', '', '', '', '', '', '',
        '1949.75', 'CHF',
        'S', 'Simon Muster', 'Musterstrasse', '1',
        '8000', 'Seldwyla', 'CH',
        'QRR', QRR, 'Instruction du 15.09', 'EPD',
    ]
    for index, value in overrides.items():
        lines[int(index)] = value
    return '\n'.join(lines)


class TestQrParser(TransactionCase):
    """Logique pure : aucune écriture en base, comme les tests du parseur
    camt et du générateur pain.001 dans le socle."""

    def test_charge_qrr_complete(self):
        data = parse_spc(payload())
        self.assertEqual(data['iban'], QR_IBAN)
        self.assertEqual(data['creditor']['name'], "Max Muster & Söhne")
        self.assertEqual(data['creditor']['zip'], '8000')
        self.assertEqual(data['creditor']['city'], 'Seldwyla')
        self.assertEqual(data['creditor']['country'], 'CH')
        self.assertAlmostEqual(data['amount'], 1949.75)
        self.assertEqual(data['currency'], 'CHF')
        self.assertEqual(data['ref_type'], 'QRR')
        self.assertEqual(data['reference'], QRR)
        self.assertEqual(data['debtor']['name'], 'Simon Muster')
        self.assertEqual(data['message'], 'Instruction du 15.09')

    def test_montant_facultatif(self):
        # Montant ouvert (dons, factures à compléter) : ligne vide.
        self.assertIsNone(parse_spc(payload(**{'18': ''}))['amount'])
        with self.assertRaises(ValueError):
            parse_spc(payload(**{'18': '1949,75'}))
        with self.assertRaises(ValueError):
            parse_spc(payload(**{'18': '1949.7'}))

    def test_coherence_qrr_qriban(self):
        # QRR sur IBAN ordinaire : refusé.
        with self.assertRaises(ValueError):
            parse_spc(payload(**{'3': IBAN}))
        # Chiffre de contrôle QRR faux : refusé.
        with self.assertRaises(ValueError):
            parse_spc(payload(**{'28': QRR[:-1] + '8'}))
        # QR-IBAN sans référence QRR : refusé.
        with self.assertRaises(ValueError):
            parse_spc(payload(**{'27': 'NON', '28': ''}))

    def test_scor_et_non(self):
        data = parse_spc(payload(**{'3': IBAN, '27': 'SCOR', '28': SCOR}))
        self.assertEqual(data['ref_type'], 'SCOR')
        self.assertEqual(data['reference'], SCOR)
        sans = parse_spc(payload(**{'3': IBAN, '27': 'NON', '28': ''}))
        self.assertEqual(sans['reference'], '')
        with self.assertRaises(ValueError):
            parse_spc(payload(**{'27': 'SCOR', '28': SCOR}))  # QR-IBAN
        with self.assertRaises(ValueError):
            parse_spc(payload(
                **{'3': IBAN, '27': 'SCOR', '28': 'RF19539007547034'}))

    def test_en_tete_trailer_et_devise(self):
        for surcharge in (
                {'0': 'XXX'}, {'1': '0100'}, {'2': '2'},
                {'19': 'USD'}, {'30': ''}, {'3': 'CH44'},
                {'5': ''}):
            with self.assertRaises(ValueError, msg=surcharge):
                parse_spc(payload(**surcharge))
        with self.assertRaises(ValueError):
            parse_spc('SPC\n0200\n1')

    def test_adresse_combinee(self):
        data = parse_spc(payload(**{
            '4': 'K', '6': 'Musterstrasse 123', '7': '8000 Seldwyla',
            '8': '', '9': ''}))
        self.assertEqual(data['creditor']['street'], 'Musterstrasse 123')
        self.assertEqual(data['creditor']['city'], '8000 Seldwyla')
        self.assertEqual(data['creditor']['zip'], '')

    def test_mod10r(self):
        self.assertEqual(mod10r(QRR[:26]), QRR[26])
        self.assertTrue(qrr_valid(QRR))
        self.assertFalse(qrr_valid(QRR[:-1] + '8'))
        self.assertFalse(qrr_valid('123'))
        self.assertTrue(scor_valid(SCOR))
        self.assertFalse(scor_valid('RF00000'))

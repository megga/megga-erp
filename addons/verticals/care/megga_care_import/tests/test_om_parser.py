from datetime import date, time

from odoo.tests import TransactionCase

from ..om_parser import (
    decode_text,
    norm,
    parse_swiss_amount,
    parse_swiss_date,
    parse_swiss_time,
    parse_table,
    slug,
    sniff_delimiter,
)


class TestOmParser(TransactionCase):
    """Logique pure : aucune écriture en base, comme les tests du parseur
    camt et du générateur pain.001 dans le socle."""

    def test_decode_text(self):
        self.assertEqual(decode_text("hélène".encode('utf-8')), "hélène")
        self.assertEqual(
            decode_text("hélène".encode('utf-16')), "hélène")
        self.assertEqual(decode_text(b'\xef\xbb\xbfnom'), "nom")
        # Octets cp1252 : l'UTF-8 strict échoue, le repli décode.
        self.assertEqual(decode_text("hélène".encode('cp1252')), "hélène")
        # Mac Roman, indiscernable à l'aveugle : choix explicite.
        self.assertEqual(
            decode_text("hélène".encode('mac_roman'), 'mac_roman'),
            "hélène")

    def test_sniff_delimiter(self):
        self.assertEqual(sniff_delimiter("a\tb\nc\td"), '\t')
        self.assertEqual(sniff_delimiter("a;b\nc;d"), ';')
        self.assertEqual(sniff_delimiter("a,b"), ',')
        self.assertEqual(sniff_delimiter("a;b", delimiter='tab'), '\t')

    def test_parse_table(self):
        headers, rows = parse_table(
            "N°\tNom Client\tPrix\n1\tKarim\t500\n\n2\tHélène\n")
        self.assertEqual(headers, ['n', 'nom client', 'prix'])
        self.assertEqual(len(rows), 2, "les lignes vides sont sautées")
        self.assertEqual(rows[0]['nom client'], 'Karim')
        # Ligne courte : complétée de vides, jamais d'erreur d'index.
        self.assertEqual(rows[1]['prix'], '')
        self.assertEqual(parse_table(""), ([], []))

    def test_parse_swiss_date(self):
        self.assertEqual(parse_swiss_date("31.12.2019"), date(2019, 12, 31))
        self.assertEqual(parse_swiss_date("5.1.24"), date(2024, 1, 5))
        # Pivot du siècle à 70 : un historique de dix ans reste en 20xx.
        self.assertEqual(parse_swiss_date("1.1.99"), date(1999, 1, 1))
        self.assertEqual(parse_swiss_date("2026-08-24"), date(2026, 8, 24))
        self.assertIsNone(parse_swiss_date(""))
        with self.assertRaises(ValueError):
            parse_swiss_date("31/12/2019")
        with self.assertRaises(ValueError):
            parse_swiss_date("31.02.2024")

    def test_parse_swiss_time(self):
        self.assertEqual(parse_swiss_time("08:00"), time(8, 0))
        self.assertEqual(parse_swiss_time("8h30"), time(8, 30))
        self.assertEqual(parse_swiss_time("14H"), time(14, 0))
        self.assertIsNone(parse_swiss_time(""))
        with self.assertRaises(ValueError):
            parse_swiss_time("25:00")
        with self.assertRaises(ValueError):
            parse_swiss_time("bientôt")

    def test_parse_swiss_amount(self):
        self.assertAlmostEqual(parse_swiss_amount("1'949.75"), 1949.75)
        self.assertAlmostEqual(parse_swiss_amount("1 949,75"), 1949.75)
        self.assertAlmostEqual(parse_swiss_amount("1.949,75"), 1949.75)
        self.assertAlmostEqual(parse_swiss_amount("CHF 500.00"), 500.0)
        self.assertAlmostEqual(parse_swiss_amount("500"), 500.0)
        self.assertIsNone(parse_swiss_amount(""))
        with self.assertRaises(ValueError):
            parse_swiss_amount("cinq cents")

    def test_norm_et_slug(self):
        self.assertEqual(norm("  N° Client  "), "n client")
        self.assertEqual(norm("Libellé"), "libelle")
        self.assertEqual(slug("Petit laboratoire"), "petit-laboratoire")

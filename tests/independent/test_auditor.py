"""Mutation checks of the QA auditor, not acceptance evidence of product behavior."""
import copy
import unittest
from decimal import Decimal

from audit_outputs import SCHEMAS, audit_tables, base_ref, decimal
from reference import build_reference


class AuditorMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = build_reference()

    def test_source_inventory(self):
        self.assertEqual(self.reference["counts"], {"checkout_rows": 1943, "checkout_unique_ids": 1943, "remittance_rows": 233, "remittance_unique_ids": 232, "banks": {"AURORA": 84, "MERIDIANO": 100}})
        self.assertEqual(len(self.reference["negative_refs"]), 4)
        self.assertEqual(len(self.reference["duplicates"]), 1)

    def test_decimal_rejects_locale_and_nonfinite(self):
        for value in ["1,01", "NaN", "Infinity", "1e5", "", " 1.00 "]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                decimal(value)
        self.assertEqual(decimal("-0.01"), Decimal("-0.01"))

    def test_unknown_outputs_remain_unavailable(self):
        result = audit_tables({}, {}, self.reference)
        self.assertEqual(len(result["findings"]), 6)
        self.assertTrue(all(f["code"] == "missing_file" for f in result["findings"]))

    def test_schema_failure_stops_semantic_checks(self):
        result = audit_tables({name: [] for name in SCHEMAS}, {name: [] for name in SCHEMAS}, self.reference)
        self.assertEqual(len(result["findings"]), 6)
        self.assertTrue(all(f["code"] == "schema" for f in result["findings"]))

    def test_empty_files_cannot_pass_by_equal_zero_totals(self):
        result = audit_tables({name: [] for name in SCHEMAS}, {name: schema.split() for name, schema in SCHEMAS.items()}, self.reference)
        codes = {f["code"] for f in result["findings"]}
        self.assertTrue({"remittance_invoice_count", "remittance_by_merchant", "bank_conservation", "unrepresented_checkout"} <= codes)

    def test_fabricated_balancing_trace_is_rejected(self):
        tables = {name: [] for name in SCHEMAS}
        tables["pendencias"] = [{"id_saida": "P-1", "tipo": "TEST", "ref_origem": "TX-FAKE", "valor_brl": "2.00", "motivo": "Fixture", "quem_decide": "QA"}]
        tables["rastro"] = [{"id_saida": "P-1", "arquivo_origem": "fake.csv", "ref_origem": "TX-FAKE", "valor": "2.00"}]
        result = audit_tables(tables, {name: schema.split() for name, schema in SCHEMAS.items()}, self.reference)
        codes = {f["code"] for f in result["findings"]}
        self.assertTrue({"unknown_trace_file", "unknown_trace_ref"} <= codes)
        self.assertNotIn("trace_sum", codes)

    def test_physical_suffix_is_not_another_operation(self):
        self.assertEqual(base_ref("PC-0926-0162@L76"), "PC-0926-0162")

    def test_half_cent_signs(self):
        from reference import rounded
        self.assertEqual(rounded(Decimal("0.005")), Decimal("0.01"))
        self.assertEqual(rounded(Decimal("-0.005")), Decimal("-0.01"))


if __name__ == "__main__":
    unittest.main()

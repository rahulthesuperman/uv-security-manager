import csv
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

from storage import Store, invoice_total, parse_money, safe_url


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.client = self.store.save("clients", {"name": "First client", "phone": "9876543210"})
        self.other = self.store.save("clients", {"name": "Other client"})
        self.site = self.store.save("sites", {"name": "Main office", "client_id": self.client})

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def asset(self, **overrides):
        data = {"client_id": self.client, "site_id": self.site, "name": "4MP camera", "quantity": "1", "serial": "UV-001", "unit_price": "3499.50"}
        data.update(overrides)
        return self.store.save("assets", data)

    def test_full_client_asset_service_lifecycle_and_persistence(self):
        ident = self.asset(specifications="4MP / PoE / outdoor", warranty_until="2027-11-14")
        job = self.store.save("services", {"client_id": self.client, "site_id": self.site, "asset_id": ident, "name": "No picture", "cost": "500"})
        row = self.store.get("assets", ident)
        self.assertEqual(row["unit_price"], 349950)
        self.assertEqual(row["specifications"], "4MP / PoE / outdoor")
        data = self.store.display_values("services", self.store.get("services", job))
        data.update(status="Completed", resolution="Replaced connector")
        self.store.save("services", data, job)
        self.store.close()
        self.store = Store(self.temp.name)
        self.assertEqual(self.store.get("services", job)["resolution"], "Replaced connector")

    def test_site_cannot_belong_to_another_client(self):
        with self.assertRaisesRegex(ValueError, "Site must belong"):
            self.asset(client_id=self.other)

    def test_service_cannot_reference_another_client_asset(self):
        ident = self.asset()
        with self.assertRaisesRegex(ValueError, "Product must belong"):
            self.store.save("services", {"client_id": self.other, "asset_id": ident, "name": "Wrong client"})

    def test_linked_site_and_asset_cannot_be_reassigned(self):
        ident = self.asset()
        site = self.store.display_values("sites", self.store.get("sites", self.site))
        site["client_id"] = self.other
        with self.assertRaisesRegex(ValueError, "cannot be changed"):
            self.store.save("sites", site, self.site)
        self.store.save("services", {"client_id": self.client, "site_id": self.site, "asset_id": ident, "name": "History"})
        data = self.store.display_values("assets", self.store.get("assets", ident))
        data.update(client_id=self.other, site_id="")
        with self.assertRaisesRegex(ValueError, "cannot be changed"):
            self.store.save("assets", data, ident)

    def test_unique_serial_and_linked_delete_protection(self):
        ident = self.asset()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.asset()
        with self.assertRaisesRegex(ValueError, "linked records"):
            self.store.delete("clients", self.client)
        self.store.delete("assets", ident)
        self.store.delete("sites", self.site)
        self.store.delete("clients", self.client)
        self.assertIsNone(self.store.get("clients", self.client))

    def test_money_tax_and_invoice_validation(self):
        ident = self.store.save("billing", {"client_id": self.client, "name": "UV/001", "subtotal": "1000.25", "tax_percent": "18", "paid": "180"})
        row = self.store.get("billing", ident)
        self.assertEqual(invoice_total(row), 118030)
        self.assertEqual(invoice_total(row) - row["paid"], 100030)
        with self.assertRaisesRegex(ValueError, "exceed"):
            self.store.save("billing", {"client_id": self.client, "name": "UV/002", "subtotal": "100", "paid": "101"})
        with self.assertRaisesRegex(ValueError, "quotation"):
            self.store.save("billing", {"client_id": self.client, "name": "Q/001", "kind": "Quotation", "subtotal": "100", "paid": "1"})

    def test_dates_and_quantities(self):
        for invalid in ("2026-02-30", "2026/11/14", "20261114"):
            with self.assertRaises(ValueError):
                self.asset(warranty_until=invalid)
        for invalid in ("0", "-1", "1.5", "hello"):
            with self.assertRaises(ValueError):
                self.asset(quantity=invalid)
        with self.assertRaisesRegex(ValueError, "before installation"):
            self.asset(installed_on="2026-11-14", warranty_until="2025-11-14")

    def test_authentication_and_password_not_stored(self):
        self.store.configure("UV Security", "example-password-123")
        self.assertTrue(self.store.authenticate("example-password-123"))
        self.assertFalse(self.store.authenticate("wrong-password"))
        self.assertNotEqual(self.store.setting("password"), "example-password-123")
        self.store.configure("UV Security", "changed-password-456")
        self.assertFalse(self.store.authenticate("example-password-123"))
        self.assertTrue(self.store.authenticate("changed-password-456"))

    def test_backup_contains_records_and_can_open(self):
        ident = self.asset()
        path = Path(self.temp.name) / "backup.sqlite3"
        self.store.backup(path)
        connection = sqlite3.connect(path)
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(connection.execute("SELECT name FROM assets WHERE id=?", (ident,)).fetchone()[0], "4MP camera")
        connection.close()
        # A finished backup must release its handle so users can move it to
        # another drive immediately, including on Windows.
        moved = path.with_name("moved-backup.sqlite3")
        path.rename(moved)
        self.assertTrue(moved.is_file())
        with self.assertRaises(ValueError):
            self.store.backup(self.store.path)

    def test_csv_amounts_and_formula_injection(self):
        self.asset(name="=HYPERLINK(\"https://example.com\")")
        target = Path(self.temp.name) / "assets.csv"
        self.store.export_csv("assets", target)
        with target.open(encoding="utf-8-sig", newline="") as stream:
            row = next(csv.DictReader(stream))
        self.assertTrue(row["name"].startswith("'="))
        self.assertEqual(row["unit_price_INR"], "3499.50")

    def test_reminders_due_and_retired_excluded(self):
        self.asset(warranty_until=str(date.today() + timedelta(days=5)))
        self.asset(serial="UV-002", status="Retired", amc_until=str(date.today() - timedelta(days=5)))
        reminders = self.store.reminders()
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0][:2], (5, "Warranty"))

    def test_urls_and_amounts(self):
        self.assertEqual(safe_url("https://device.example.com/live"), "https://device.example.com/live")
        for url in ("javascript:alert(1)", "file:///tmp/test", "https://user:secret@example.com", "http://example.com", "rtsp://example.com"):
            with self.assertRaises(ValueError):
                safe_url(url)
        for value in ("NaN", "-1", "0.001", "infinity", "1e20"):
            with self.assertRaises(ValueError):
                parse_money(value)

    def test_unknown_table_and_missing_record(self):
        with self.assertRaises(ValueError):
            self.store.rows("settings; DROP TABLE clients")
        with self.assertRaisesRegex(ValueError, "no longer exists"):
            self.store.save("clients", {"name": "Missing"}, 999)


if __name__ == "__main__":
    unittest.main()

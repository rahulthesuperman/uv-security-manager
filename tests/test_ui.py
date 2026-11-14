"""Opt-in native Tk smoke tests: UV_UI_TEST=1 with a working display."""
import os
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from app import App, RecordEditor


@unittest.skipUnless(os.environ.get("UV_UI_TEST") == "1", "Native display tests are opt-in")
class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(self.temp.name)
        self.errors = []
        self.app.report_callback_exception = lambda *args: self.errors.append(args)
        self.app.update()
        self.app.store.configure("UV Test", "test-password-123")
        self.client = self.app.store.save("clients", {"name": "Example client"})
        self.site = self.app.store.save("sites", {"name": "Example office", "client_id": self.client})
        self.asset = self.app.store.save("assets", {"name": "Test camera", "client_id": self.client, "site_id": self.site, "quantity": "1"})
        self.app.shell()
        self.app.update()

    def tearDown(self):
        self.app.shutdown()
        self.temp.cleanup()
        self.assertFalse(self.errors, self.errors)

    def test_every_navigation_page_and_client_filter(self):
        for page in ("dashboard", "clients", "sites", "assets", "services", "billing", "settings"):
            self.app.navigate(page)
            self.app.update()
        self.app.navigate("assets", self.client)
        self.assertEqual(len(self.app.visible_rows), 1)
        self.app.search.set("missing-record")
        self.app.fill_records()
        self.assertEqual(len(self.app.tree.get_children()), 0)

    def test_all_editors_render_and_dependent_links(self):
        for table in ("clients", "sites", "assets", "services", "billing"):
            editor = RecordEditor(self.app, table, preset={"client_id": self.client, "site_id": self.site})
            self.app.update()
            if "site_id" in editor.inputs:
                self.assertEqual(editor.link_id("site_id"), self.site)
            editor.destroy()

    def test_edit_product_save_and_full_record(self):
        self.app.navigate("assets")
        row = self.app.store.get("assets", self.asset)
        editor = RecordEditor(self.app, "assets", row)
        editor.inputs["model"].insert(0, "UV-MODEL-4MP")
        editor.save()
        self.app.update()
        row = self.app.store.get("assets", self.asset)
        self.assertEqual(row["model"], "UV-MODEL-4MP")
        self.app.details("assets", row)
        self.app.update()
        self.assertIn("UV-MODEL-4MP", self.app.detail_text("assets", row))

    def test_live_url_opens_browser_and_lock_hides_workspace(self):
        row = self.app.store.get("sites", self.site)
        row["live_url"] = "https://example.com/authorized-camera"
        with patch("app.webbrowser.open") as opened:
            self.app.live(row)
            opened.assert_called_once_with(row["live_url"])
        self.app.lock()
        self.app.update()
        self.assertIsNone(self.app.client_filter)


if __name__ == "__main__":
    unittest.main()

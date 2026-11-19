"""Offline persistence and validation for UV Security Manager (stdlib only)."""
from __future__ import annotations

import csv
from contextlib import closing
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
from datetime import date, datetime
from urllib.parse import urlsplit

APP_VERSION = "1.0.0"
WEBSITE = "https://uv-security-system.satiny-coin-6290.chatgpt.site/"

# label, input type; link types are resolved by the desktop editor.
FIELDS = {
    "clients": [("name", "Client / company *", "text"), ("contact", "Contact person", "text"), ("phone", "Phone", "text"), ("email", "Email", "text"), ("address", "Billing address", "long"), ("gstin", "GSTIN", "text"), ("notes", "Notes", "long")],
    "sites": [("client_id", "Client *", "clients"), ("name", "Site name *", "text"), ("address", "Site address", "long"), ("contact", "Site contact", "text"), ("phone", "Site phone", "text"), ("live_url", "Authorized live view URL (HTTPS)", "url"), ("notes", "Notes (no passwords)", "long")],
    "assets": [("client_id", "Client *", "clients"), ("site_id", "Installation site", "sites"), ("name", "Product name *", "text"), ("category", "Category", "category"), ("brand", "Brand", "text"), ("model", "Model", "text"), ("serial", "Serial / asset tag", "text"), ("quantity", "Quantity *", "integer"), ("specifications", "Full specifications", "long"), ("location", "Room / installation position", "text"), ("supplier", "Supplier", "text"), ("purchase_date", "Purchase date (YYYY-MM-DD)", "date"), ("installed_on", "Installation date", "date"), ("unit_price", "Unit selling price (INR)", "money"), ("invoice_ref", "Invoice reference", "text"), ("warranty_until", "Warranty expiry", "date"), ("amc_until", "AMC expiry", "date"), ("next_service", "Next service date", "date"), ("status", "Status", "asset_status"), ("document_path", "Invoice / photo / document", "file"), ("notes", "Additional details (no passwords)", "long")],
    "services": [("client_id", "Client *", "clients"), ("site_id", "Site", "sites"), ("asset_id", "Product / asset", "assets"), ("name", "Complaint / job title *", "text"), ("description", "Complaint details", "long"), ("opened_on", "Opened on", "date"), ("due_on", "Due on", "date"), ("technician", "Assigned technician", "text"), ("status", "Status", "service_status"), ("resolution", "Work performed / replacement details", "long"), ("cost", "Service charge (INR)", "money")],
    "billing": [("client_id", "Client *", "clients"), ("name", "Unique invoice / quotation number *", "text"), ("kind", "Document type", "billing_kind"), ("issued_on", "Issue date", "date"), ("due_on", "Due date", "date"), ("description", "Products / work / payment terms", "long"), ("subtotal", "Subtotal (INR)", "money"), ("tax_percent", "Tax percent", "money"), ("paid", "Amount received (INR)", "money"), ("notes", "Notes", "long")],
}
CHOICES = {
    "category": ["CCTV camera", "DVR / NVR", "Hard disk", "Computer", "Networking", "Access control", "Alarm", "UPS / Power", "Cable / Accessory", "Other"],
    "asset_status": ["Installed", "In stock", "Under repair", "Replaced", "Retired"],
    "service_status": ["Open", "Scheduled", "In progress", "Completed", "Cancelled"],
    "billing_kind": ["Invoice", "Quotation"],
}
MONEY = {"unit_price", "cost", "subtotal", "paid", "tax_percent"}
DATES = {field for fields in FIELDS.values() for field, _, kind in fields if kind == "date"}


def default_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "UVSecurityManager"


def safe_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an HTTPS URL without a username or password. Sign in on the device page.")
    if any(ord(c) < 32 for c in value):
        raise ValueError("Invalid URL.")
    return value


def rupees(paise: int) -> str:
    return f"INR {paise / 100:,.2f}"


def parse_money(value) -> int:
    from decimal import Decimal, InvalidOperation
    try:
        number = Decimal(str(value or "0").replace(",", ""))
        if not number.is_finite() or number < 0 or number > Decimal("999999999"):
            raise ValueError("Amount must be between 0 and 999,999,999.")
        if number.as_tuple().exponent < -2:
            raise ValueError("Use at most two decimal places.")
        return int(number * 100)
    except InvalidOperation as exc:
        raise ValueError("Enter a valid amount, e.g. 2500.00.") from exc


def invoice_total(row) -> int:
    return row["subtotal"] + (row["subtotal"] * row["tax_percent"] + 5000) // 10000


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clients (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, contact TEXT DEFAULT '', phone TEXT DEFAULT '',
 email TEXT DEFAULT '', address TEXT DEFAULT '', gstin TEXT DEFAULT '', notes TEXT DEFAULT '',
 updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sites (
 id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id), name TEXT NOT NULL,
 address TEXT DEFAULT '', contact TEXT DEFAULT '', phone TEXT DEFAULT '', live_url TEXT DEFAULT '',
 notes TEXT DEFAULT '', updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assets (
 id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
 site_id INTEGER REFERENCES sites(id), name TEXT NOT NULL, category TEXT DEFAULT '', brand TEXT DEFAULT '',
 model TEXT DEFAULT '', serial TEXT DEFAULT '', quantity INTEGER NOT NULL DEFAULT 1,
 specifications TEXT DEFAULT '', location TEXT DEFAULT '', supplier TEXT DEFAULT '',
 purchase_date TEXT DEFAULT '', installed_on TEXT DEFAULT '', unit_price INTEGER DEFAULT 0,
 invoice_ref TEXT DEFAULT '', warranty_until TEXT DEFAULT '', amc_until TEXT DEFAULT '',
 next_service TEXT DEFAULT '', status TEXT DEFAULT 'Installed', document_path TEXT DEFAULT '',
 notes TEXT DEFAULT '', updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS unique_asset_serial ON assets(serial) WHERE serial != '';
CREATE TABLE IF NOT EXISTS services (
 id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
 site_id INTEGER REFERENCES sites(id), asset_id INTEGER REFERENCES assets(id), name TEXT NOT NULL,
 description TEXT DEFAULT '', opened_on TEXT DEFAULT '', due_on TEXT DEFAULT '',
 technician TEXT DEFAULT '', status TEXT DEFAULT 'Open', resolution TEXT DEFAULT '',
 cost INTEGER DEFAULT 0, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS billing (
 id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id), name TEXT NOT NULL UNIQUE,
 kind TEXT DEFAULT 'Invoice', issued_on TEXT DEFAULT '', due_on TEXT DEFAULT '', description TEXT DEFAULT '',
 subtotal INTEGER DEFAULT 0, tax_percent INTEGER DEFAULT 0, paid INTEGER DEFAULT 0,
 notes TEXT DEFAULT '', updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS assets_client ON assets(client_id);
CREATE INDEX IF NOT EXISTS sites_client ON sites(client_id);
CREATE INDEX IF NOT EXISTS services_client ON services(client_id);
CREATE INDEX IF NOT EXISTS billing_client ON billing(client_id);
PRAGMA user_version = 1;
"""


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else default_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "uv-security.sqlite3"
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            self.db.close()
            raise ValueError("This database needs a newer version of UV Security Manager.")
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self):
        self.db.close()

    def setting(self, key, default=""):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def configure(self, company, password):
        if len(password) < 10:
            raise ValueError("Use a password with at least 10 characters.")
        salt = secrets.token_hex(24)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()
        with self.db:
            for key, value in (("company", company.strip() or "UV Security System"), ("salt", salt), ("password", digest)):
                self.db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))

    def authenticate(self, password):
        salt = self.setting("salt")
        if not salt:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()
        return hmac.compare_digest(digest, self.setting("password"))

    def rows(self, table):
        self._table(table)
        return [dict(r) for r in self.db.execute(f"SELECT * FROM {table} ORDER BY id DESC")]

    def get(self, table, ident):
        self._table(table)
        row = self.db.execute(f"SELECT * FROM {table} WHERE id=?", (ident,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _table(table):
        if table not in FIELDS:
            raise ValueError("Unknown record type.")

    def display_values(self, table, row):
        result = {}
        for key, _, kind in FIELDS[table]:
            value = row.get(key, "")
            if kind == "money":
                value = f"{(value or 0) / 100:.2f}"
            result[key] = value if value is not None else ""
        return result

    def save(self, table, values, ident=None):
        self._table(table)
        if ident is not None and self.get(table, ident) is None:
            raise ValueError("Record no longer exists.")
        data = {}
        for key, label, kind in FIELDS[table]:
            raw = str(values.get(key, "") or "").strip()
            if "*" in label and not raw:
                raise ValueError(f"{label.replace(' *', '')} is required.")
            if kind in FIELDS:
                if not raw:
                    data[key] = None
                else:
                    try:
                        related_id = int(raw)
                    except ValueError as exc:
                        raise ValueError(f"Select a valid {label}.") from exc
                    if not self.get(kind, related_id):
                        raise ValueError(f"Selected {label} does not exist.")
                    data[key] = related_id
            elif kind == "integer":
                try:
                    data[key] = int(raw)
                except ValueError as exc:
                    raise ValueError("Quantity must be a whole number.") from exc
                if not 1 <= data[key] <= 1_000_000:
                    raise ValueError("Quantity must be between 1 and 1,000,000.")
            elif kind == "money":
                data[key] = parse_money(raw)
                if key == "tax_percent" and data[key] > 10000:
                    raise ValueError("Tax percent must be between 0 and 100.")
            elif kind == "date":
                if raw:
                    try:
                        if date.fromisoformat(raw).isoformat() != raw:
                            raise ValueError()
                    except ValueError as exc:
                        raise ValueError(f"{label}: use a valid YYYY-MM-DD date.") from exc
                data[key] = raw
            elif kind in CHOICES:
                data[key] = raw or CHOICES[kind][0]
                if data[key] not in CHOICES[kind]:
                    raise ValueError(f"Invalid {label}.")
            elif kind == "url":
                data[key] = safe_url(raw)
            else:
                if len(raw) > 20_000:
                    raise ValueError(f"{label} is too long (maximum 20,000 characters).")
                data[key] = raw
        if data.get("email") and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", data["email"]):
            raise ValueError("Enter a valid email address.")
        client_id = data.get("client_id")
        if data.get("site_id"):
            site = self.get("sites", data["site_id"])
            if site["client_id"] != client_id:
                raise ValueError("Site must belong to the selected client.")
        if data.get("asset_id"):
            asset = self.get("assets", data["asset_id"])
            if asset["client_id"] != client_id:
                raise ValueError("Product must belong to the selected client.")
            if data.get("site_id") and asset["site_id"] != data["site_id"]:
                raise ValueError("Product must belong to the selected site.")
        if table == "sites" and ident:
            if self.get(table, ident)["client_id"] != client_id and self.db.execute(
                "SELECT 1 FROM assets WHERE site_id=? UNION ALL SELECT 1 FROM services WHERE site_id=? LIMIT 1", (ident, ident)
            ).fetchone():
                raise ValueError("This site has products or service jobs. Its client cannot be changed.")
        if table == "assets" and ident:
            for job in self.db.execute("SELECT client_id, site_id FROM services WHERE asset_id=?", (ident,)):
                if job["client_id"] != client_id or (job["site_id"] and job["site_id"] != data["site_id"]):
                    raise ValueError("This product has service history. Its client/site cannot be changed.")
        for end in ("warranty_until", "amc_until", "next_service"):
            if data.get(end) and data.get("installed_on") and data[end] < data["installed_on"]:
                raise ValueError(f"{end.replace('_', ' ').title()} cannot be before installation.")
        for start, end in (("opened_on", "due_on"), ("issued_on", "due_on")):
            if data.get(start) and data.get(end) and data[end] < data[start]:
                raise ValueError("Due date cannot be before the opening / issue date.")
        if table == "billing":
            if data["paid"] > invoice_total(data):
                raise ValueError("Amount received cannot exceed the total.")
            if data["kind"] == "Quotation" and data["paid"]:
                raise ValueError("Convert the quotation to an invoice before recording a payment.")
        data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            with self.db:
                if ident:
                    assignments = ",".join(f"{key}=?" for key in data)
                    self.db.execute(f"UPDATE {table} SET {assignments} WHERE id=?", (*data.values(), ident))
                else:
                    columns = ",".join(data)
                    placeholders = ",".join("?" for _ in data)
                    ident = self.db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(data.values())).lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError("Serial / asset tag or invoice number already exists, or a linked record is invalid.") from exc
        return ident

    def delete(self, table, ident):
        self._table(table)
        try:
            with self.db:
                self.db.execute(f"DELETE FROM {table} WHERE id=?", (ident,))
        except sqlite3.IntegrityError as exc:
            raise ValueError("This record has linked records. Remove those first, or keep this record for history.") from exc

    def backup(self, target):
        target = Path(target)
        if target.resolve() == self.path.resolve():
            raise ValueError("Choose a different file for the backup.")
        # sqlite3.Connection's context manager commits; it does not close the
        # file handle. Explicit closure is essential before Windows can move
        # or replace the finished backup.
        with closing(sqlite3.connect(target)) as destination:
            self.db.backup(destination)
        return target

    def reminders(self):
        today = date.today()
        result = []
        for row in self.rows("assets"):
            if row["status"] in ("Retired", "Replaced"):
                continue
            for key, label in (("warranty_until", "Warranty"), ("amc_until", "AMC"), ("next_service", "Maintenance")):
                if row[key]:
                    days = (date.fromisoformat(row[key]) - today).days
                    if days <= 30:
                        result.append((days, label, row))
        return sorted(result, key=lambda r: r[0])

    def export_csv(self, table, path, rows=None):
        self._table(table)
        records = self.rows(table) if rows is None else rows
        columns = ["id"] + [f[0] for f in FIELDS[table]] + ["updated_at"]
        # Prevent spreadsheet formula execution from user-provided names/notes.
        def cell(value):
            text = str(value if value is not None else "")
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
        with open(path, "w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow([key + ("_INR" if key in MONEY and key != "tax_percent" else "") for key in columns])
            for row in records:
                writer.writerow([cell(f"{row[key] / 100:.2f}" if key in MONEY else row.get(key, "")) for key in columns])

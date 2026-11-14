"""UV Security Manager: a single-computer Windows desktop application."""
from __future__ import annotations

import argparse
from datetime import date
import html
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

from storage import APP_VERSION, CHOICES, FIELDS, Store, WEBSITE, invoice_total, rupees, safe_url

NAV = {"dashboard": "Overview", "clients": "Clients", "sites": "Sites & live view", "assets": "Products & assets", "services": "Service jobs", "billing": "Invoices & quotations", "settings": "Settings & backup"}
COLUMNS = {
    "clients": [("name", "Client / company", 220), ("contact", "Contact", 170), ("phone", "Phone", 140), ("email", "Email", 220)],
    "sites": [("name", "Site", 200), ("client_name", "Client", 200), ("address", "Address", 280), ("live", "Live connection", 140)],
    "assets": [("name", "Product", 190), ("client_name", "Client", 180), ("site_name", "Site", 160), ("model", "Model", 140), ("serial", "Serial / tag", 150), ("quantity", "Qty", 60), ("status", "Status", 110), ("warranty_until", "Warranty expiry", 130)],
    "services": [("name", "Job", 230), ("client_name", "Client", 200), ("technician", "Technician", 160), ("due_on", "Due date", 120), ("status", "Status", 120)],
    "billing": [("name", "Document no.", 170), ("client_name", "Client", 210), ("kind", "Type", 110), ("issued_on", "Issued", 120), ("total_display", "Total", 140), ("balance_display", "Balance", 140)],
}
BG, INK, MUTED, BLUE, NAVY = "#f2f5fa", "#172b45", "#62738a", "#2265d8", "#10233e"


def open_file(path):
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise ValueError("File not found. Keep attached documents on this computer.")
    if target.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".csv", ".html"}:
        raise ValueError("Open PDF, images, text or CSV documents only.")
    if os.name == "nt":
        os.startfile(str(target))
    else:
        subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class RecordEditor(tk.Toplevel):
    def __init__(self, app, table, row=None, preset=None):
        super().__init__(app)
        self.app, self.table, self.row = app, table, row
        self.inputs, self.maps = {}, {}
        self.title(("Edit " if row else "Add ") + NAV[table])
        self.geometry("740x760")
        self.minsize(580, 460)
        self.configure(bg=BG)
        self.transient(app)
        self.grab_set()
        heading = ttk.Frame(self, padding=20)
        heading.pack(fill="x")
        ttk.Label(heading, text=("Edit record" if row else "New record"), style="Heading.TLabel").pack(anchor="w")
        ttk.Label(heading, text="Fields marked * are required. Dates: YYYY-MM-DD.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True, padx=20)
        canvas = tk.Canvas(outer, bg="white", highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        form = ttk.Frame(canvas, padding=20, style="White.TFrame")
        window = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        def wheel(event):
            canvas.yview_scroll(-1 if event.delta > 0 or event.num == 4 else 1, "units")
        self.bind("<MouseWheel>", wheel)
        self.bind("<Button-4>", wheel)
        self.bind("<Button-5>", wheel)
        data = app.store.display_values(table, row) if row else dict(preset or {})
        defaults = {"quantity": "1", "status": "Open" if table == "services" else "Installed", "opened_on": str(date.today()), "issued_on": str(date.today()), "kind": "Invoice"}
        for key, label, kind in FIELDS[table]:
            ttk.Label(form, text=label, style="White.TLabel").pack(anchor="w", pady=(10, 4))
            value = data.get(key, defaults.get(key, ""))
            if kind == "long":
                widget = tk.Text(form, height=3, wrap="word", font=("Segoe UI", 10), relief="solid", bd=1, highlightthickness=0)
                widget.insert("1.0", str(value))
                widget.pack(fill="x")
            elif kind in FIELDS or kind in CHOICES:
                widget = ttk.Combobox(form, state="readonly")
                if kind in FIELDS:
                    self.maps[key] = {}
                    # Dependent selectors are populated and refreshed below.
                else:
                    widget["values"] = CHOICES[kind]
                    widget.set(value or CHOICES[kind][0])
                widget.pack(fill="x")
            else:
                holder = ttk.Frame(form, style="White.TFrame")
                holder.pack(fill="x")
                widget = ttk.Entry(holder)
                widget.insert(0, str(value))
                widget.pack(side="left", fill="x", expand=True)
                if kind == "file":
                    ttk.Button(holder, text="Browse…", command=lambda w=widget: self.browse(w)).pack(side="right", padx=(8, 0))
            self.inputs[key] = widget
        self.refresh_links(data)
        if "client_id" in self.inputs:
            self.inputs["client_id"].bind("<<ComboboxSelected>>", lambda e: self.refresh_links())
        if "site_id" in self.inputs:
            self.inputs["site_id"].bind("<<ComboboxSelected>>", lambda e: self.refresh_links())
        footer = ttk.Frame(self, padding=20)
        footer.pack(fill="x")
        ttk.Button(footer, text="Save record", style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="right", padx=10)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-Return>", lambda e: self.save())

    def browse(self, widget):
        path = filedialog.askopenfilename(parent=self, title="Select document or photo", filetypes=[("Documents / photos", "*.pdf *.png *.jpg *.jpeg *.webp *.txt *.csv"), ("All files", "*.*")])
        if path:
            widget.delete(0, "end")
            widget.insert(0, path)

    def link_id(self, key):
        return self.maps.get(key, {}).get(self.inputs[key].get()) if key in self.inputs else None

    def refresh_links(self, initial=None):
        selected = initial or {key: self.link_id(key) for key in self.maps}
        for key, _, kind in FIELDS[self.table]:
            if kind not in FIELDS:
                continue
            rows = self.app.store.rows(kind)
            client_id = selected.get("client_id")
            site_id = selected.get("site_id")
            if kind in ("sites", "assets"):
                rows = [r for r in rows if r["client_id"] == client_id]
            if kind == "assets" and site_id:
                rows = [r for r in rows if r["site_id"] == site_id]
            mapping = {f"#{r['id']} · {r['name']}": r["id"] for r in rows}
            self.maps[key] = mapping
            self.inputs[key]["values"] = [""] + list(mapping)
            self.inputs[key].set(next((label for label, ident in mapping.items() if ident == selected.get(key)), ""))

    def save(self):
        data = {}
        for key, widget in self.inputs.items():
            if key in self.maps:
                data[key] = self.link_id(key)
            else:
                data[key] = widget.get("1.0", "end-1c") if isinstance(widget, tk.Text) else widget.get()
        try:
            self.app.store.save(self.table, data, self.row["id"] if self.row else None)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Check record", str(exc), parent=self)
            return
        self.destroy()
        self.app.refresh()
        self.app.status.set("Record saved on this computer.")


class App(tk.Tk):
    def __init__(self, directory=None):
        super().__init__()
        self.title("UV Security Manager")
        self.geometry("1280x820")
        self.minsize(960, 650)
        self.configure(bg=BG)
        self.store = Store(directory)
        self.page, self.client_filter = "dashboard", None
        self.search, self.status = tk.StringVar(), tk.StringVar(value="Offline workspace · Records stored on this computer")
        self.style_setup()
        self.protocol("WM_DELETE_WINDOW", self.shutdown)
        self.show_login()

    def style_setup(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=BG, foreground=INK)
        style.configure("TButton", padding=(13, 9))
        style.configure("Accent.TButton", background=BLUE, foreground="white", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#164ca7")])
        style.configure("TEntry", padding=7, fieldbackground="white")
        style.configure("TCombobox", padding=6, fieldbackground="white")
        style.configure("Heading.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Subheading.TLabel", font=("Segoe UI", 13, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("White.TFrame", background="white")
        style.configure("White.TLabel", background="white")
        style.configure("Treeview", rowheight=36, background="white", fieldbackground="white", borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=10, background="#e7eef7")
        style.map("Treeview", background=[("selected", BLUE)], foreground=[("selected", "white")])

    def clear(self):
        for child in self.winfo_children():
            child.destroy()

    def show_login(self):
        self.clear()
        setup = not self.store.setting("password")
        panel = ttk.Frame(self, padding=36)
        panel.place(relx=.5, rely=.5, anchor="center", width=520)
        ttk.Label(panel, text="UV SECURITY", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Desktop client & asset manager", style="Subheading.TLabel").pack(anchor="w", pady=(6, 24))
        ttk.Label(panel, text="Create your local administrator login" if setup else "Sign in to your local workspace", style="Muted.TLabel").pack(anchor="w", pady=(0, 18))
        company = tk.StringVar(value="UV Security System")
        if setup:
            ttk.Label(panel, text="Company name").pack(anchor="w")
            ttk.Entry(panel, textvariable=company).pack(fill="x", pady=(4, 14))
        ttk.Label(panel, text="Password (minimum 10 characters)" if setup else "Administrator password").pack(anchor="w")
        password, confirm = tk.StringVar(), tk.StringVar()
        entry = ttk.Entry(panel, textvariable=password, show="●")
        entry.pack(fill="x", pady=(4, 14))
        if setup:
            ttk.Label(panel, text="Confirm password").pack(anchor="w")
            ttk.Entry(panel, textvariable=confirm, show="●").pack(fill="x", pady=(4, 14))
        error = tk.StringVar()
        ttk.Label(panel, textvariable=error, wraplength=440, foreground="#b63745").pack(anchor="w", pady=8)
        button = ttk.Button(panel, text="Create workspace" if setup else "Unlock workspace", style="Accent.TButton")
        def unlock(event=None):
            try:
                if setup:
                    if password.get() != confirm.get():
                        raise ValueError("Passwords do not match.")
                    self.store.configure(company.get(), password.get())
                elif not self.store.authenticate(password.get()):
                    button.state(["disabled"])
                    self.after(2000, lambda: button.state(["!disabled"]) if button.winfo_exists() else None)
                    raise ValueError("Incorrect password. Please try again.")
                password.set("")
                confirm.set("")
                self.shell()
            except ValueError as exc:
                error.set(str(exc))
        button.configure(command=unlock)
        button.pack(fill="x")
        entry.bind("<Return>", unlock)
        ttk.Label(panel, text="Your records stay on this PC. Keep your password and backups safe.\nThe database is not encrypted; use Windows disk encryption.", style="Muted.TLabel", wraplength=440).pack(anchor="w", pady=(20, 0))
        entry.focus_set()

    def shell(self):
        self.clear()
        sidebar = tk.Frame(self, bg=NAVY, width=224)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="UV  /  SECURITY", fg="white", bg=NAVY, font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(32, 5))
        tk.Label(sidebar, text="CLIENT & ASSET MANAGER", fg="#9eb5d5", bg=NAVY, font=("Segoe UI", 9)).pack(anchor="w", padx=22, pady=(0, 28))
        self.nav_buttons = {}
        for page, label in NAV.items():
            button = tk.Button(sidebar, text=label, anchor="w", padx=22, pady=13, bg=NAVY, fg="#d6e3f5", activebackground="#244569", activeforeground="white", relief="flat", bd=0, font=("Segoe UI", 11), command=lambda p=page: self.navigate(p))
            button.pack(fill="x", padx=9, pady=2)
            self.nav_buttons[page] = button
        tk.Button(sidebar, text="Open UV website ↗", command=lambda: webbrowser.open(WEBSITE), bg=NAVY, fg="#a5c8ff", relief="flat", anchor="w", padx=22, pady=15).pack(fill="x", padx=9, pady=(24, 0))
        tk.Button(sidebar, text="Lock workspace", command=self.lock, bg=NAVY, fg="white", relief="flat", padx=20, pady=12).pack(side="bottom", fill="x", padx=9, pady=18)
        right = ttk.Frame(self)
        right.pack(side="right", fill="both", expand=True)
        top = ttk.Frame(right, padding=(26, 16))
        top.pack(fill="x")
        ttk.Label(top, text=self.store.setting("company"), style="Subheading.TLabel").pack(side="left")
        ttk.Label(top, text="LOCAL WORKSPACE  •  " + date.today().strftime("%d %b %Y"), style="Muted.TLabel").pack(side="right")
        self.content = ttk.Frame(right, padding=(26, 12))
        self.content.pack(fill="both", expand=True)
        ttk.Label(right, textvariable=self.status, style="Muted.TLabel", padding=(26, 12)).pack(fill="x")
        self.navigate("dashboard")

    def lock(self):
        self.client_filter = None
        self.search.set("")
        self.show_login()

    def navigate(self, page, client_id=None):
        self.page, self.client_filter = page, client_id
        self.search.set("")
        self.refresh()

    def refresh(self):
        for child in self.content.winfo_children():
            child.destroy()
        for page, button in self.nav_buttons.items():
            button.configure(bg="#244569" if page == self.page else NAVY)
        title = NAV[self.page]
        if self.client_filter:
            client = self.store.get("clients", self.client_filter)
            title += "  /  " + (client["name"] if client else "Client")
        ttk.Label(self.content, text=title, style="Heading.TLabel").pack(anchor="w", pady=(4, 8))
        if self.page == "dashboard":
            self.dashboard()
        elif self.page == "settings":
            self.settings()
        else:
            self.records()

    def dashboard(self):
        ttk.Label(self.content, text="Manage every installation, product and customer relationship in one place.", style="Muted.TLabel").pack(anchor="w", pady=(0, 22))
        cards = ttk.Frame(self.content)
        cards.pack(fill="x")
        clients, assets, jobs, bills = (self.store.rows(t) for t in ("clients", "assets", "services", "billing"))
        balance = sum(invoice_total(r) - r["paid"] for r in bills if r["kind"] == "Invoice")
        stats = [("CLIENTS", str(len(clients)), "clients"), ("PRODUCT UNITS", str(sum(r["quantity"] for r in assets)), "assets"), ("OPEN JOBS", str(sum(r["status"] not in ("Completed", "Cancelled") for r in jobs)), "services"), ("OUTSTANDING", rupees(balance), "billing")]
        for i, (label, value, page) in enumerate(stats):
            cards.columnconfigure(i, weight=1)
            card = ttk.Frame(cards, padding=16, style="White.TFrame")
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 12 if i < 3 else 0))
            ttk.Label(card, text=label, foreground=MUTED, style="White.TLabel").pack(anchor="w")
            ttk.Label(card, text=value, font=("Segoe UI", 20, "bold"), style="White.TLabel").pack(anchor="w", pady=8)
            ttk.Button(card, text="View →", command=lambda p=page: self.navigate(p)).pack(anchor="w")
        quick = ttk.Frame(self.content)
        quick.pack(fill="x", pady=20)
        ttk.Button(quick, text="+ Add client", style="Accent.TButton", command=lambda: RecordEditor(self, "clients")).pack(side="left", padx=(0, 10))
        ttk.Button(quick, text="+ Add product", command=lambda: RecordEditor(self, "assets")).pack(side="left", padx=(0, 10))
        ttk.Button(quick, text="+ Service job", command=lambda: RecordEditor(self, "services")).pack(side="left")
        ttk.Label(self.content, text="Warranty, AMC & maintenance reminders", style="Subheading.TLabel").pack(anchor="w", pady=(8, 5))
        ttk.Label(self.content, text="Expired / overdue and due in the next 30 days. Reminders update when the app is open.", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        tree = self.make_tree(self.content, [("product", "Product / client", 330), ("kind", "Reminder", 150), ("date", "Date", 130), ("due", "Timing", 160)])
        self.reminder_assets = {}
        client_names = {r["id"]: r["name"] for r in clients}
        for i, (days, label, row) in enumerate(self.store.reminders()):
            key = {"Warranty": "warranty_until", "AMC": "amc_until", "Maintenance": "next_service"}[label]
            tree.insert("", "end", iid=str(i), values=(row["name"] + " / " + client_names.get(row["client_id"], ""), label, row[key], f"{abs(days)} days overdue" if days < 0 else "Today" if days == 0 else f"In {days} days"))
            self.reminder_assets[str(i)] = row
        tree.bind("<Double-1>", lambda e: self.details("assets", self.reminder_assets[tree.selection()[0]]) if tree.selection() else None)
        if not assets:
            ttk.Label(self.content, text="Start by adding a client, then a site and the products installed there. No demo records have been added.", style="Muted.TLabel", wraplength=800).pack(anchor="w", pady=12)

    def make_tree(self, parent, columns):
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True)
        tree = ttk.Treeview(holder, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        yscroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        for key, label, width in columns:
            tree.heading(key, text=label, command=lambda k=key: self.sort_tree(tree, k))
            tree.column(key, width=width, minwidth=60)
        return tree

    @staticmethod
    def sort_tree(tree, key):
        descending = getattr(tree, "_sort", None) == (key, False)
        def sort_key(item):
            value = tree.set(item, key)
            numeric = value.replace("INR ", "").replace(",", "")
            try:
                return (0, float(numeric))
            except ValueError:
                return (1, value.casefold())
        for index, item in enumerate(sorted(tree.get_children(), key=sort_key, reverse=descending)):
            tree.move(item, "", index)
        tree._sort = (key, descending)

    def records(self):
        toolbar = ttk.Frame(self.content)
        toolbar.pack(fill="x", pady=(8, 16))
        entry = ttk.Entry(toolbar, textvariable=self.search, width=30)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry.bind("<KeyRelease>", lambda e: self.fill_records())
        ttk.Button(toolbar, text="Search", command=self.fill_records).pack(side="left", padx=(0, 10))
        ttk.Button(toolbar, text="+ Add record", style="Accent.TButton", command=lambda: RecordEditor(self, self.page, preset={"client_id": self.client_filter} if self.client_filter else None)).pack(side="right")
        self.tree = self.make_tree(self.content, COLUMNS[self.page])
        self.tree.bind("<Double-1>", lambda e: self.selected_action("view"))
        self.tree.bind("<Return>", lambda e: self.selected_action("view"))
        actions = ttk.Frame(self.content)
        actions.pack(fill="x", pady=(14, 0))
        for label, action in [("View details", "view"), ("Edit", "edit"), ("Delete", "delete")]:
            ttk.Button(actions, text=label, command=lambda a=action: self.selected_action(a)).pack(side="left", padx=(0, 8))
        if self.page == "sites":
            ttk.Button(actions, text="Open live view ↗", command=lambda: self.selected_action("live")).pack(side="left")
        ttk.Button(actions, text="Export visible CSV", command=self.export).pack(side="right")
        if self.client_filter:
            ttk.Button(actions, text="Show all clients", command=lambda: self.navigate(self.page)).pack(side="right", padx=8)
        self.count_text = tk.StringVar()
        ttk.Label(self.content, textvariable=self.count_text, style="Muted.TLabel").pack(anchor="w", pady=(12, 0))
        self.fill_records()

    def fill_records(self):
        clients = {r["id"]: r["name"] for r in self.store.rows("clients")}
        sites = {r["id"]: r["name"] for r in self.store.rows("sites")}
        query = self.search.get().strip().casefold()
        self.visible_rows = []
        self.tree.delete(*self.tree.get_children())
        for row in self.store.rows(self.page):
            if self.client_filter and row.get("client_id") != self.client_filter:
                continue
            display = dict(row, client_name=clients.get(row.get("client_id"), ""), site_name=sites.get(row.get("site_id"), ""), live="Link configured" if row.get("live_url") else "Not connected")
            if self.page == "billing":
                display["total_display"] = rupees(invoice_total(row))
                display["balance_display"] = rupees(invoice_total(row) - row["paid"]) if row["kind"] == "Invoice" else "—"
            if query and query not in " ".join(str(v) for v in display.values()).casefold():
                continue
            self.visible_rows.append(row)
            self.tree.insert("", "end", iid=str(row["id"]), values=[display.get(key, "") for key, _, _ in COLUMNS[self.page]])
        self.count_text.set(f"{len(self.visible_rows)} records · Search any detail · Double-click a row for its complete record")

    def selected_action(self, action):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select record", "Select a row first.", parent=self)
            return
        row = self.store.get(self.page, int(selection[0]))
        if not row:
            self.refresh()
            return
        if action == "view":
            self.details(self.page, row)
        elif action == "edit":
            RecordEditor(self, self.page, row)
        elif action == "live":
            self.live(row)
        elif action == "delete" and messagebox.askyesno("Delete record?", f"Permanently delete {row['name']}?\nLinked records prevent deletion. Back up important records first.", parent=self):
            try:
                self.store.delete(self.page, row["id"])
                self.refresh()
            except ValueError as exc:
                messagebox.showerror("Cannot delete", str(exc), parent=self)

    def detail_text(self, table, row):
        lines = [self.store.setting("company"), NAV[table] + f" / Record #{row['id']}", ""]
        for key, label, kind in FIELDS[table]:
            value = row.get(key, "")
            if kind in FIELDS and value:
                related = self.store.get(kind, value)
                value = f"{related['name']} (#{value})" if related else str(value)
            elif kind == "money":
                value = f"{value / 100:.2f}%" if key == "tax_percent" else rupees(value)
            lines.append(label.replace(" *", "") + ": " + str(value or "—"))
        if table == "billing":
            lines += ["", "Total: " + rupees(invoice_total(row)), "Balance: " + (rupees(invoice_total(row) - row["paid"]) if row["kind"] == "Invoice" else "Quotation — not due")]
        if table in ("clients", "assets", "sites"):
            for related in ("sites", "assets", "services", "billing"):
                key = "client_id" if table == "clients" else "site_id" if table == "sites" else "asset_id"
                if related == table or (table != "clients" and related not in ("assets", "services")) or (table == "assets" and related != "services"):
                    continue
                matching = [r for r in self.store.rows(related) if r.get(key) == row["id"]]
                lines += ["", NAV[related] + f" ({len(matching)})"]
                for item in matching:
                    lines.append(f"  #{item['id']} · {item['name']}" + (f" · {item['serial']} · Qty {item['quantity']} · {item['status']}" if related == "assets" else f" · {item.get('status', '')}"))
        lines += ["", "Last updated: " + row["updated_at"]]
        return "\n".join(lines)

    def details(self, table, row):
        window = tk.Toplevel(self)
        window.title(row["name"] + " — Full record")
        window.geometry("850x700")
        window.minsize(650, 500)
        window.transient(self)
        body = ttk.Frame(window, padding=22)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=row["name"], style="Heading.TLabel", wraplength=760).pack(anchor="w", pady=(0, 14))
        holder = ttk.Frame(body)
        holder.pack(fill="both", expand=True)
        text = tk.Text(holder, wrap="word", font=("Segoe UI", 11), padx=16, pady=16, relief="flat", bg="white", fg=INK)
        scrollbar = ttk.Scrollbar(holder, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        report = self.detail_text(table, row)
        text.insert("1.0", report)
        text.configure(state="disabled")
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(16, 0))
        def edit():
            window.destroy()
            RecordEditor(self, table, row)
        ttk.Button(buttons, text="Edit record", command=edit).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save printable report", command=lambda: self.report(report, row["id"])).pack(side="left", padx=(0, 8))
        if table == "clients":
            linked = ttk.Frame(body)
            linked.pack(fill="x", pady=(10, 0))
            for target in ("sites", "assets", "services", "billing"):
                def visit(t=target):
                    window.destroy()
                    self.navigate(t, row["id"])
                ttk.Button(linked, text=NAV[target], command=visit).pack(side="left", padx=(0, 6))
        if table == "sites":
            ttk.Button(buttons, text="Open live view ↗", command=lambda: self.live(row)).pack(side="left")
        if table == "assets" and row["document_path"]:
            def document():
                try:
                    open_file(row["document_path"])
                except (ValueError, OSError) as exc:
                    messagebox.showerror("Cannot open document", str(exc), parent=window)
            ttk.Button(buttons, text="Open attachment", command=document).pack(side="left")

    def report(self, content, ident):
        path = filedialog.asksaveasfilename(parent=self, title="Save printable report", defaultextension=".html", initialfile=f"UV-record-{ident}.html", filetypes=[("Printable HTML", "*.html")])
        if path:
            try:
                Path(path).write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>UV Security record</title><style>body{font:15px system-ui;max-width:900px;margin:40px auto;padding:20px;color:#172b45}pre{font:inherit;white-space:pre-wrap;line-height:1.7}button{padding:10px 20px}@media print{button{display:none}body{margin:0}}</style><button onclick="window.print()">Print / Save as PDF</button><pre>' + html.escape(content) + '</pre></html>', encoding="utf-8")
                webbrowser.open(Path(path).resolve().as_uri())
                self.status.set("Report saved. Use Print / Save as PDF in your browser.")
            except OSError as exc:
                messagebox.showerror("Report failed", str(exc), parent=self)

    def live(self, row):
        try:
            url = safe_url(row["live_url"])
            if not url:
                raise ValueError("No connection configured. Edit this site and add the authorized HTTPS portal for its camera / NVR. RTSP streams need a separate compatible gateway or vendor application.")
            webbrowser.open(url)
            self.status.set("Opened authorized device portal. The app does not verify camera connectivity.")
        except ValueError as exc:
            messagebox.showinfo("Live view setup", str(exc), parent=self)

    def export(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile=f"UV-{self.page}-{date.today()}.csv", filetypes=[("Excel-compatible CSV", "*.csv")])
        if path:
            try:
                self.store.export_csv(self.page, path, self.visible_rows)
                self.status.set(f"Exported {len(self.visible_rows)} records to {path}")
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc), parent=self)

    def settings(self):
        ttk.Label(self.content, text="Single-computer edition  •  Version " + APP_VERSION, style="Muted.TLabel").pack(anchor="w", pady=(0, 20))
        box = ttk.Frame(self.content, padding=24, style="White.TFrame")
        box.pack(fill="x")
        ttk.Label(box, text="Data & backups", font=("Segoe UI", 15, "bold"), style="White.TLabel").pack(anchor="w")
        ttk.Label(box, text="Database: " + str(self.store.path), style="White.TLabel", wraplength=760).pack(anchor="w", pady=(12, 8))
        ttk.Label(box, text="Create a backup before changing computers. Attachments are file references: copy those files separately. Backups include the administrator password hash and client records.", style="White.TLabel", wraplength=760).pack(anchor="w", pady=(0, 16))
        ttk.Button(box, text="Create database backup…", style="Accent.TButton", command=self.backup).pack(anchor="w")
        ttk.Label(box, text="Restore: close the app, preserve the current database, then replace uv-security.sqlite3 in the folder above with your backup. Your backup's administrator password will apply.", style="White.TLabel", wraplength=760).pack(anchor="w", pady=(16, 0))
        form = ttk.Frame(self.content, padding=(0, 22))
        form.pack(fill="x")
        ttk.Label(form, text="Change company name / administrator password", style="Subheading.TLabel").pack(anchor="w", pady=(0, 12))
        values = {}
        for key, label in (("company", "Company name"), ("current", "Current password"), ("password", "New password (10+ characters)"), ("confirm", "Confirm new password")):
            ttk.Label(form, text=label).pack(anchor="w", pady=(5, 3))
            values[key] = tk.StringVar(value=self.store.setting("company") if key == "company" else "")
            ttk.Entry(form, textvariable=values[key], show="" if key == "company" else "●", width=45).pack(anchor="w")
        def change():
            try:
                if not self.store.authenticate(values["current"].get()):
                    raise ValueError("Current password is incorrect.")
                if values["password"].get() != values["confirm"].get():
                    raise ValueError("New passwords do not match.")
                self.store.configure(values["company"].get(), values["password"].get())
                self.shell()
                self.navigate("settings")
                self.status.set("Company and administrator password updated.")
            except ValueError as exc:
                messagebox.showerror("Cannot update", str(exc), parent=self)
        ttk.Button(form, text="Update account", command=change).pack(anchor="w", pady=12)

    def backup(self):
        path = filedialog.asksaveasfilename(parent=self, title="Save database backup", defaultextension=".sqlite3", initialfile=f"UV-backup-{date.today()}.sqlite3", filetypes=[("SQLite backup", "*.sqlite3")])
        if path:
            try:
                self.store.backup(path)
                self.status.set("Backup saved to " + path)
                messagebox.showinfo("Backup saved", "Database backup created. Copy referenced documents/photos separately.", parent=self)
            except (OSError, ValueError) as exc:
                messagebox.showerror("Backup failed", str(exc), parent=self)

    def shutdown(self):
        self.store.close()
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="UV Security Manager desktop application")
    parser.add_argument("--data-dir", help="Use a separate local data directory (for testing / portable use)")
    args = parser.parse_args()
    try:
        App(args.data_dir).mainloop()
    except Exception as exc:
        import traceback
        log = Path(os.environ.get("TEMP", ".")) / "UVSecurityManager-error.log"
        try:
            log.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("UV Security Manager", f"Unable to continue: {exc}\n\nDetails: {log}", parent=root)
            root.destroy()
        except tk.TclError:
            print(f"Unable to start desktop: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

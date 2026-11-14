# UV Security Manager — Desktop v1.0

A real native desktop application for a **single Windows 10/11 computer**, built with Python/Tkinter and SQLite. No subscription, web server or runtime package installation is required when using the built executable. All records are local. No real clients or camera credentials are included.

## Run on Windows now (source edition)

**Setup option:** extract the package and double-click **Setup-Windows.bat** on 64-bit Windows 10/11. This downloads Python 3.14.3 from python.org, verifies its Windows Authenticode signature and Python Software Foundation publisher, installs a per-user desktop runtime, copies the app, and creates desktop/Start Menu shortcuts. Internet is required for initial setup. No GitHub account or administrator access is needed. Existing client data is preserved. This setup script has been supplied for Windows, but it has not been executed on Windows in the authoring environment. If your Windows policy blocks PowerShell or software installation, use the source steps below with your administrator's approved Python installation.

Manual source option:

1. Extract this entire ZIP into a folder, e.g. `Documents\UV-Security-Manager`.
2. Install **Python 3.12 or newer** from https://www.python.org/downloads/windows/ using the official installer. Include Tcl/Tk and select **Add Python to PATH**.
3. Double-click **Start-UV-Security.bat**.
4. On first launch, set your company name and administrator password (10 or more characters). There is no default password or cloud password reset.
5. Add a **client**, then its **sites**, then its **products**. All lists start empty.

## Build a standalone EXE

On a Windows computer with Python installed, double-click **Build-Windows.bat**. It installs PyInstaller into a build-only virtual environment, runs tests, and produces `dist\UV-Security-Manager.exe`. The finished EXE can run without Python. This is a portable unsigned EXE, not an installer; a code-signing certificate and MSI installer are not included.

Alternatively, place these files at the **root of a GitHub repository**, including `.github/workflows/windows-build.yml`. Open **Actions → Build Windows Desktop → Run workflow**. After a successful run, download the `UV-Security-Manager-Windows` artifact and extract its EXE. The build needs internet access; the application itself works offline except when opening external links.

The Windows build workflow is supplied but has not been executed by the authoring Linux environment. A Windows EXE is not included in this source ZIP.

## Included features

- Local administrator setup, password change and manual workspace lock. Passwords use salted PBKDF2-SHA256 (600,000 iterations).
- Clients: company, contact, phone, email, billing address, GSTIN and notes.
- Sites linked to clients: location, site contact and an authorized HTTPS live-view portal URL.
- Products linked to client/site: category, brand, model, unique serial or asset tag, quantity, specifications, installation position, supplier, purchase/install dates, selling price, invoice reference, warranty/AMC dates, next service, status, attachment reference and notes.
- Service jobs linked to client/site/product: complaint, technician, due date, work performed, status and charge.
- Invoice/quotation **summary records**: number, description, subtotal, tax percentage, amount received and balance. Exact integer currency calculations; quotations excluded from outstanding totals. This version does not provide invoice line-item accounting, automatic GST compliance, stock purchasing or payment gateway processing.
- Search every record field, sort columns, view client-specific records, view full product details and linked service history.
- Dashboard with product-unit counts, open jobs, outstanding invoice amounts, and warranty/AMC/maintenance reminders due within 30 days (including overdue records).
- Excel-compatible CSV export of visible records, and printable HTML reports (use browser Print → Save as PDF).
- SQLite database backup, with a documented manual restore procedure below.
- Opens your existing website: https://uv-security-system.satiny-coin-6290.chatgpt.site/

## Live cameras and website connection

**Sites & live view → Add/Edit → Authorized live view URL** accepts an HTTPS link to an existing camera/NVR vendor portal or your authorized streaming gateway. Select the site and choose **Open live view**. It opens in the system browser, where you authenticate normally.

This is not an embedded CCTV player and it does not discover cameras, monitor whether devices are online, or convert RTSP/ONVIF streams. Device-specific direct streaming requires its model, supported protocol and an authorized gateway/vendor integration. The app labels a configured link, never a verified live feed. Never place usernames/passwords in URLs or notes.

The existing website is opened by link; its source and public access settings have not been changed. Website client data is not automatically imported or synchronized.

## Data, attachments and backup

Windows database location: `%LOCALAPPDATA%\UVSecurityManager\uv-security.sqlite3`.

Use **Settings & backup → Create database backup** and copy the backup to another drive. Attachments are references to files on disk, not embedded uploads; keep those files in a stable folder and back up that folder separately. One attachment reference is supported per product; use the notes field for further document references.

**Restore:**

1. Close all copies of the application.
2. Copy the existing `uv-security.sqlite3` to a safe location first.
3. Copy a known-good backup into the data folder and rename it `uv-security.sqlite3`.
4. Reopen the app and sign in using the password that was active when the backup was made.
5. Restore attached files to their original paths, or edit each attachment reference.

The local login is an application access gate. **The SQLite database, exports and backups are not encrypted.** Use your own Windows account, Windows device encryption/BitLocker and restricted folder access. Anyone with direct file access can read the database. There is no multi-user permission system, remote sync or network-shared database support. Reminders are shown while the app is open; there are no email/SMS/background notifications.

## Hindi quick start

1. ZIP extract karein; Python install karke `Start-UV-Security.bat` double-click karein.
2. Apna company name aur password banayein.
3. **Clients** mein client add karein → **Sites** mein uski location → **Products & assets** mein har product ki poori detail bharein.
4. Client par double-click karke uske products, sites, jobs aur invoices khol sakte hain.
5. Har hafte **Settings & backup** se backup doosri drive par save karein.
6. Camera dekhne ke liye site mein authorized HTTPS live-view portal add karein. Direct RTSP playback is version mein nahi hai.

## Development and verification

Python 3.12+ with Tkinter. Runtime uses only the Python standard library.

```sh
python -m unittest discover -s tests -v
python app.py
# Isolated test database:
python app.py --data-dir /path/to/test-folder
```

`storage.py` owns validation, relationships, authentication, billing and persistence; `app.py` owns the native desktop UI. Keep the database off shared/network drives. The app uses schema version 1 and refuses to open newer database formats.

### Verification performed

17 automated checks passed on Linux with a native Tk display: 13 data/authentication/backup/billing checks and 4 desktop UI smoke checks covering every navigation page, all record editors, product editing, client filters, detail views, live-link handoff and lock. Windows executable packaging and setup still require a Windows run. To run the native UI checks, set `UV_UI_TEST=1` before the unittest command.

### Remove the application

Close the app. Remove its desktop and Start Menu shortcuts and delete `%LOCALAPPDATA%\UVSecurityManager\app`. Use Windows Installed apps to remove the private Python runtime if desired. Keep `uv-security.sqlite3` and your backups unless you deliberately want to erase your client records. Do not delete the whole `UVSecurityManager` folder when retaining data.

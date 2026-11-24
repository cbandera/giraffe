# Giraffe – Specification (v1)

Working title: **Giraffe** (Giro + giraffe: the long neck reaches any IBAN).

A local Linux desktop app that extracts payment data from invoices (PDF, clipboard) and
generates a **GiroCode** (EPC QR code per EPC069-12) that can be scanned with a banking
app on the phone. Fully offline.

## Goals

- Invoices arrive by e-mail (Thunderbird), as attachments, or otherwise as PDF.
- With minimal effort (no terminal) produce a QR code that opens a prefilled SEPA
  transfer in the banking app.
- The user sees and can correct the detected fields **before** scanning.
- No network access, no cloud, no telemetry.

## Environment

- Ubuntu 26.04, GNOME, **Wayland only** (no X11 assumptions, no xdotool/xclip).
- Python 3 (system version), GUI with **GTK4 + libadwaita** via PyGObject
  (`python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`).
- Other dependencies: `segno` (QR), `pypdf` (embedded files/metadata), `defusedxml`,
  `poppler-utils` (`pdftotext -layout`), optional `wl-clipboard` as fallback.
- venv created with `--system-site-packages` so PyGObject is visible.
- Project layout (`src` layout, `pyproject.toml`):

```
giraffe/
  pyproject.toml
  src/giraffe/
    __main__.py        # CLI entry, arguments
    app.py             # Adw.Application, window lifecycle
    window.py          # UI
    extract/
      zugferd.py       # read embedded XML (CII/UBL)
      text.py          # regex fallback on text
      models.py        # PaymentData dataclass incl. per-field source
    epc.py             # build + validate payload, render QR
    iban.py            # normalization + mod-97
    amounts.py         # German/international number formats
  data/
    giraffe.desktop
    icons/
  scripts/install.sh   # .desktop, icon, GNOME shortcut
  tests/
```

## Entry points (v1)

1. **"Open with…" / file manager:** `giraffe.desktop` with `MimeType=application/pdf;`,
   `Exec=giraffe %f`. Invocation: `giraffe /path/invoice.pdf`.
   Note: depending on version and settings, Thunderbird may open attachments only with the
   default application. Workaround: save the attachment, then use "Open with" in the file
   manager. Investigate whether a practical route from Thunderbird exists without replacing
   the user's default PDF viewer.
2. **Drag & drop** onto the window (`Gtk.DropTarget` for `Gio.File` and text/URI list).
   To verify: what Thunderbird provides when dragging an attachment (temporary `file://`
   URL?). The empty window shows a drop area ("Drop a PDF here or press Ctrl+V").
3. **Clipboard via global hotkey:** `giraffe --clipboard` reads the text content of the
   clipboard (Gdk.Clipboard, fallback `wl-paste`) and parses it. The user selects text in a
   viewer or mail (Ctrl+A, Ctrl+C) and presses the hotkey.
   - Default shortcut `<Ctrl><Alt>g`, registered as a **custom GNOME keybinding** via
     `gsettings` (`org.gnome.settings-daemon.plugins.media-keys custom-keybindings`) in
     `install.sh`. Append to existing custom shortcuts, never overwrite. Idempotent.
   - In the window as well: Ctrl+V pastes text from the clipboard and re-parses.
   - Single instance via `Gio.Application` with a unique app ID
     (`io.github.<user>.Giraffe`): a second invocation activates the running instance
     (D-Bus activation) instead of opening a second window.

Not in v1: screenshot + OCR (entry point 4), Thunderbird add-on.

## Lifecycle: no tray icon needed

Decision: **v1 has no tray icon.** The hotkey launches the app directly.

Reasoning and trade-offs:

- The app is a short-lived tool: hotkey, check, scan, close. A resident process with a tray
  icon adds complexity without a clear benefit.
- GNOME has no native system tray. Ubuntu ships the AppIndicator extension enabled by
  default, but GTK4 has no tray API. A tray icon means implementing StatusNotifierItem
  over D-Bus by hand or mixing in `libayatana-appindicator` (GTK3), which does not coexist
  with GTK4 in one process. It also breaks on Ubuntu variants or setups without the extension.
- Startup of a Python + GTK4 app is typically a few hundred milliseconds, which is
  acceptable for a hotkey-triggered dialog.
- With `Gio.Application` single-instance behavior, repeated hotkey presses reuse the same
  process anyway.

Optional, cheap, still without tray: a `--gapplication-service` / `--background` mode.
The process stays resident with no window (`Gio.Application.hold()`), so the hotkey shows
the window instantly. It is optional and off by default, and can be revisited if startup
latency turns out to bother the user.

A tray icon is a possible later addition (v2+), preferably as a small separate helper
process, only if a real need appears (e.g. a persistent "recent invoices" menu).

## Extraction (strategy order)

1. **E-invoice (ZUGFeRD / Factur-X / XRechnung):** check the PDF for embedded files
   (`factur-x.xml`, `zugferd-invoice.xml`, `xrechnung.xml`) and parse the XML (no network
   access, no external entities, use `defusedxml`).
   - CII: payee (`SellerTradeParty/Name`), IBAN
     (`PayeePartyCreditorFinancialAccount/IBANID`), BIC
     (`PayeeSpecifiedCreditorFinancialInstitution/BICID`), amount due
     (`DuePayableAmount`, else `GrandTotalAmount`), currency, invoice number
     (`ExchangedDocument/ID`), payment reference (`PaymentReference`).
   - UBL (XRechnung): `PayeeFinancialAccount/ID`, `PayableAmount`, `cbc:ID`, `PaymentID`.
   - Model source: `source="e-invoice"`.
2. **Text fallback** (`pdftotext -layout`, or the clipboard text directly):
   - IBAN: regex tolerant of whitespace, then mod-97 validation. Keep all candidates.
   - Amount: candidates near keywords (Gesamtbetrag, Rechnungsbetrag, Zahlbetrag,
     Endbetrag, zu zahlen, Brutto, Total, Amount due). Support German (`1.234,56`) and
     English (`1,234.56`) formats. EUR only; warn on other currencies.
   - Remittance text: invoice number after keywords (Rechnungsnummer, Rechnung Nr.,
     Invoice No., Beleg). Default: `Rechnung <number>`.
   - Payee name: hard to do reliably. Heuristic (line before/next to the IBAN, header/footer),
     otherwise leave empty. The user fills it in.
   - Model source: `source="text"`, optionally with a confidence value.
3. With several IBAN or amount candidates: show a dropdown instead of silently guessing.
4. Scanned PDFs without text: v1 only shows "No text found" (OCR comes in v2).

Every field carries a **source** (`e-invoice` | `text` | `manual`), shown subtly in the UI
so the user knows how reliable the value is.

## EPC QR payload (epc.py)

Line by line, separator `\n`, UTF-8:

```
BCD
002
1
SCT
<BIC or empty>
<name, max 70 characters>
<IBAN without spaces>
EUR<amount with dot, 2 decimals, 0.01 to 999999999.99>
<purpose code, empty>
<structured reference, max 35 characters, OR empty>
<unstructured remittance text, max 140 characters, OR empty>
<beneficiary-to-originator info, empty>
```

- Structured reference and remittance text are **mutually exclusive**.
- Total length max **331 bytes** (UTF-8). Otherwise show an error in the UI (never truncate
  silently).
- QR: error correction **M**, sufficient quiet zone, white background (dark mode must not
  invert the QR).
- `segno.helpers.make_epc_qr` may be used. Alternatively write your own builder to control
  version 002 and the length limits. Secure it with a golden test.
- An empty amount is allowed (the payer enters it), but the UI shows a hint.

## UI (GTK4 + libadwaita)

- One compact main window. Form on the left, large QR code on the right.
- Fields: payee, IBAN, BIC (optional), amount (EUR), remittance text. All editable, the QR
  updates live.
- Inline validation: invalid IBAN (checksum), missing amount, payload too long, currency not
  EUR. With invalid data no QR is shown, only the reason.
- Candidate dropdowns when several IBANs/amounts were detected.
- Actions: save QR as PNG, copy QR image to clipboard, re-read input.
- Visible notice: "Check IBAN and payee name in your banking app before paying."
- Empty state: drop area with a hint about Ctrl+V and the hotkey.
- Light/dark follows the system; the QR area is always black on white.
- Keyboard: Ctrl+V paste, Ctrl+O open file, Ctrl+Q quit.

## Security and privacy

- No network access. No telemetry. No persistence of invoice data (no history in v1, no logs
  containing IBANs/amounts).
- Inputs are **untrusted** (foreign PDFs/mails):
  - Subprocesses (`pdftotext`) only with an argument list, never through a shell, with a
    timeout and an input size limit.
  - XML only via `defusedxml`.
  - Never execute or fetch anything from the PDF.
- Fraud protection: the user confirms by checking in the banking app. No automatic
  transfers, no hiding uncertainty. Show the source of every field.
- Temporary files (e.g. from drag & drop) only in a dedicated temp directory, deleted after
  use.

## Installation

- `scripts/install.sh` (for the development state, no root):
  1. `giraffe.desktop` to `~/.local/share/applications/`, icon to
     `~/.local/share/icons/hicolor/...`, `update-desktop-database`.
  2. Optionally register the GNOME shortcut (see above).
  3. Launcher script that uses the venv (`~/.local/bin/giraffe`).
- Later (not v1): `.deb` or Flatpak. With Flatpak, remember that the sandbox and portals
  restrict file access and the clipboard.

## Tests (pytest)

- `iban`: valid/invalid IBANs, whitespace, lowercase.
- `amounts`: `1.234,56`, `1,234.56`, `12,5`, `12.50 €`, thousands-separator traps.
- `epc`: compare the golden payload exactly, length limits (70/140/35/331 bytes), umlauts
  and multibyte characters, reference-XOR-remittance.
- `zugferd`: synthetic CII and UBL samples (no real invoices in the repo).
- `text`: synthetic invoice texts in several layouts, multiple IBAN candidates.
- Optional GUI smoke test that starts the window without interaction.
- Never commit real invoices. Keep hand-test material locally outside the repo.

## Acceptance criteria v1

- `giraffe invoice.pdf` opens the window with detected fields and a valid QR.
- The generated QR is read by the user's real banking app and correctly prefills payee,
  IBAN, amount and remittance text.
- A ZUGFeRD PDF yields its fields from the XML, a normal PDF via the text path.
- Drag & drop from Thunderbird works, or the limitation is documented.
- Hotkey + selected text on the clipboard opens the window with detected fields.
- An invalid IBAN produces no QR but a clear message.
- The hotkey launches the app directly; a second invocation reuses the running instance.
- Works without network (test with network blocked).

## Open points for the local session

- Check Thunderbird behavior for "Open with" and drag & drop.
- Check clipboard behavior under GNOME/Wayland when launched via hotkey (focus, access).
  Fallback `wl-paste`.
- Measure cold start time. Only if it is annoying, enable the optional background mode.
- Confirm project naming (app ID, Python package name).
- v2 preparation: screenshot via `org.freedesktop.portal.Screenshot` plus `tesseract-ocr`
  and `tesseract-ocr-deu`, using the IBAN checksum as an OCR error filter. Tray icon only
  if a concrete need appears.

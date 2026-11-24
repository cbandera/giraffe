# Giraffe

Local Linux desktop app (GTK4 + libadwaita, Wayland) that reads payment data from invoices
and shows a **GiroCode** (EPC QR) for your banking app. Fully offline. See `SPEC.md`.

## Setup

```
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 poppler-utils   # wl-clipboard optional
scripts/install.sh            # venv, launcher, .desktop, icon, Ctrl+Alt+G shortcut
```

## Usage

- `giraffe invoice.pdf` – open a PDF (ZUGFeRD/XRechnung XML first, text fallback)
- `giraffe --clipboard` – parse the clipboard text (bound to Ctrl+Alt+G)
- Drag & drop a PDF or text onto the window, Ctrl+V to paste, Ctrl+O to open
- `giraffe --background` – stay resident without a window (optional, faster hotkey)

## Development

```
.venv/bin/pytest
```

Not in v1: OCR for scanned PDFs, tray icon, history. Thunderbird drag & drop and
"Open with" behavior are untested (see open points in `SPEC.md`).

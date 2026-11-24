# Contributing

## Development setup

```
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 poppler-utils python3-venv
python3 -m venv --system-site-packages .venv      # system site packages expose PyGObject
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/python -m giraffe invoice.pdf           # run from the source tree
```

`scripts/install.sh` does an editable install, so code changes take effect on the next start
without reinstalling. Restart any resident `--background` process.

## Layout

```
src/giraffe/
  app.py            Adw.Application: command line, single instance, clipboard
  window.py         UI (form, QR widget, drag & drop, actions)
  epc.py            EPC069-12 payload builder, validation, QR rendering
  iban.py           normalization, mod-97, IBAN detection in text
  amounts.py        German/international number parsing
  extract/
    zugferd.py      embedded e-invoice XML (CII / UBL)
    text.py         regex heuristics on text
    models.py       PaymentData with per-field source
    __init__.py     entry points: from_file, from_text
scripts/            install.sh, register_shortcut.py, screenshot.py
data/               desktop entry and icon
tests/
```

Extraction order: embedded e-invoice XML first, then `pdftotext -layout` plus the text
heuristics. See `SPEC.md` for the full specification.

## Tests

`pytest` runs unit tests for IBAN, amounts, EPC payload (including a golden payload and byte
limits), e-invoice parsing and text extraction, plus a GUI smoke test that is skipped without
a display.

- **Never commit real invoices or personal data**: no real names, addresses, IBANs, or
  invoice numbers. Use synthetic text and public example IBANs such as
  `DE89 3704 0044 0532 0130 00`. Keep hand-test material outside the repo.
  `*.pdf` is git-ignored as a safety net.
- Improving detection: add a synthetic text that reproduces the layout (for example
  `pdftotext -layout` output with all values replaced) as a failing test, then adjust
  `extract/text.py`.

## Security rules

Inputs are untrusted. Keep these invariants:

- no network access, no telemetry, no logging of IBANs or amounts
- subprocesses only with an argument list, a timeout and a size limit; never a shell
- XML only through `defusedxml`
- never silently truncate payload fields; show an error instead
- temporary files only in a private temp directory, deleted after use

## Screenshot

`docs/screenshot.png` is generated from synthetic data:

```
.venv/bin/python scripts/screenshot.py
```

## Style

Keep changes small and covered by tests. Match the existing code style.

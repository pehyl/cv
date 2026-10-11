# Petr Hýl – CV

One source, every format. The CV content lives in `data/cv.cs.json` and `data/cv.en.json`
(based on the [JSON Resume](https://jsonresume.org) schema). `build.py` turns it into:

| Output | Where | Contact details |
|---|---|---|
| Web pages `/cs/`, `/en/` with schema.org JSON-LD | `dist/` | city and country, e-mail, LinkedIn |
| PDF (tagged, with metadata) | `dist/<lang>/` | same as web |
| `cv.md`, `resume.json`, `llms.txt` for AI agents | `dist/` | same as web |
| PDF + Markdown for sending directly | `private/` (git-ignored) | full address and phone |

## Build

```bash
pip install -r requirements.txt
python3 -m playwright install chromium   # once
python3 build.py
```

Fonts (Bricolage Grotesque, Source Sans 3) are self-hosted in `assets/fonts/` from Fontsource.

## Tailoring for a specific position

Copy a data file (e.g. `data/cv.en.json`), adjust `basics.label`, `basics.summary`, the order of
`skills` and the `highlights`, then build from it. The layout never needs touching.

## Publish

Set `"url"` in `site.json` to the Pages address (e.g. `https://<user>.github.io/cv/`), rebuild,
commit and push to `main`. The workflow in `.github/workflows/pages.yml` deploys `dist/`.
In the repository settings, set **Pages → Source** to **GitHub Actions**.

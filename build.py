#!/usr/bin/env python3
"""Build Petr Hýl's CV from data/cv.<lang>.json.

    python3 build.py

Outputs
  dist/     public website for GitHub Pages: no street address, no phone.
            /, /cs/, /en/ (HTML + PDF + cv.md + resume.json), llms.txt, robots.txt, sitemap.xml
  private/  PDFs (and Markdown) with full contact details, for sending directly. Never commit.

Set the site address in site.json ("url") so canonical links, JSON-LD and the sitemap use it.
"""
import json, re, shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject

ROOT = Path(__file__).parent
SITE = json.loads((ROOT / 'site.json').read_text())
LANGS = ['cs', 'en']
COUNTRY = {'cs': 'Česká republika', 'en': 'Czech Republic'}
PDF_NAME = {'cs': 'Petr-Hyl-Frontend-developer-CV-cs.pdf', 'en': 'Petr-Hyl-Frontend-Developer-CV-en.pdf'}
MD_NAME = {'cs': 'Petr-Hyl-CV-cs.md', 'en': 'Petr-Hyl-CV-en.md'}


def ym(v):
    m = re.fullmatch(r'(\d{4})-(\d{2})', v)
    return f'{int(m.group(2))}/{m.group(1)}' if m else v


def site_url(path=''):
    return (SITE['url'].rstrip('/') + '/' + path) if SITE['url'] else ''


def load(lang):
    return json.loads((ROOT / f'data/cv.{lang}.json').read_text())


def jsonld(cv, url):
    b = cv['basics']
    d = {
        '@context': 'https://schema.org', '@type': 'Person',
        'name': b['name'], 'jobTitle': b['label'], 'description': b['summary'], 'email': 'mailto:' + b['email'],
        'address': {'@type': 'PostalAddress', 'addressLocality': b['location']['city'], 'addressCountry': b['location']['countryCode']},
        'sameAs': [p['url'] for p in b['profiles']],
        'knowsAbout': [k for s in cv['skills'] for k in s['keywords']],
        'knowsLanguage': [l['language'] for l in cv['languages']],
        'alumniOf': [{'@type': 'CollegeOrUniversity', 'name': n} for n in dict.fromkeys(e['institution'] for e in cv['education'])],
        'worksFor': {'@type': 'Organization', 'name': cv['work'][0]['name']},
        'hasOccupation': {'@type': 'Occupation', 'name': b['label'], 'skills': ', '.join(k for s in cv['skills'] for k in s['keywords'])},
    }
    if url:
        d['url'] = url
    return json.dumps(d, ensure_ascii=False, indent=1)


def markdown(cv, private):
    b, ui, loc = cv['basics'], cv['ui'], cv['basics']['location']
    where = f"{loc['address']}, {loc['postalCode']} {loc['city']}" if (private and loc.get('address')) else f"{loc['city']}, {COUNTRY[cv['lang']]}"
    L = [f"# {b['name']}", '', f"**{b['label']}**", '', f"- {where}"]
    if private:
        L.append(f"- {b['phone']}")
    L += [f"- {b['email']}"] + [f"- {p['network']}: {p['url']}" for p in b['profiles']] + ['']
    L += [f"## {ui['profile']}", '', b['summary'], '', f"## {ui['ai']}", ''] + [f"- {i}" for i in cv['ai']['items']]
    L += ['', f"## {ui['skills']}", ''] + [f"- **{s['name']}:** {', '.join(s['keywords'])}" for s in cv['skills']]
    L += ['', f"## {ui['work']}", '']
    for w in cv['work']:
        if not w.get('highlights'):
            continue
        L += [f"### {w['position']} – {w['name']} ({ym(w['startDate'])} – {ui['present']})", '', w['summary'], ''] + [f"- {h}" for h in w['highlights']] + ['']
    L += [f"## {ui['pastWork']}", ''] + [f"- {ym(w['startDate'])} – {ym(w['endDate']) if w.get('endDate') else ui['present']}: {w['position']}, {w['name']}" for w in cv['work'] if not w.get('highlights')]
    L += ['', f"## {ui['projects']}", ''] + [f"- [{p['name']}]({p['url']}) – {p['description']}" for p in cv['projects']]
    L += ['', f"### {ui['sideProjects']}", ''] + [f"- [{p['name']}]({p['url']}) – {p['description']}" for p in cv['sideProjects']]
    L += ['', f"## {ui['education']}", ''] + [f"- {e['startDate']}–{e['endDate']}: {e['area']}, {e['institution']} ({e['studyType']})" for e in cv['education']]
    L += ['', f"## {ui['certificates']}", ''] + [f"- [{c['name']}]({c['url']}), {c['issuer']}" for c in cv['certificates']]
    L += ['', f"## {ui['languages']}", ''] + [f"- {l['language']}: {l['fluency']}" for l in cv['languages']]
    L += ['', f"## {ui['interests']}", '', '; '.join(i['name'] for i in cv['interests']), '']
    return '\n'.join(L)


def resume_json(cv):
    """JSON Resume (public: no phone or street)."""
    r = {k: v for k, v in json.loads(json.dumps(cv)).items() if k not in ('ui', 'lang', 'ai')}
    b = r['basics']
    for k in ('phone', 'image'):
        b.pop(k, None)
    for k in ('address', 'postalCode'):
        b['location'].pop(k, None)
    if SITE['url']:
        b['url'] = site_url(cv['lang'] + '/')
    # JSON Resume has no AI section; keep it as the first skill group's context and in meta
    r['meta'] = {'language': cv['lang'], 'aiWorkflow': cv['ai']['items'], 'canonical': b.get('url', '')}
    r['$schema'] = 'https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json'
    return json.dumps(r, ensure_ascii=False, indent=2)


def render(env, cv, private, alternates, pdf_name):
    lang = cv['lang']
    return env.get_template('cv.html.j2').render(
        cv=cv, b=cv['basics'], ui=cv['ui'], fonts=SITE['theme_fonts'], root='../',
        show_private=private, country=COUNTRY[lang], alternates=alternates, pdf_name=pdf_name,
        canonical=site_url(lang + '/'), jsonld=jsonld(cv, site_url(lang + '/')))


def print_pdf(page, html_path, pdf_path, cv):
    page.goto(html_path.as_uri())
    page.wait_for_load_state('networkidle')
    page.evaluate('document.fonts.ready')
    page.pdf(path=str(pdf_path), format='A4', print_background=True, prefer_css_page_size=True, tagged=True, outline=True)
    w = PdfWriter(clone_from=PdfReader(str(pdf_path)))
    w.add_metadata({'/Title': cv['ui']['docTitle'], '/Author': cv['basics']['name'], '/Subject': cv['basics']['label'],
                    '/Keywords': cv['ui']['keywords'], '/Creator': 'HTML/CSS, Chromium'})
    w._root_object[NameObject('/Lang')] = TextStringObject(cv['lang'])
    w.write(str(pdf_path))


def copy_assets(out):
    shutil.copytree(ROOT / 'assets/fonts', out / 'fonts', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'css', out / 'css', dirs_exist_ok=True)
    for f in ('photo.jpg', 'favicon.svg'):
        shutil.copy(ROOT / 'assets' / f, out / f)


def root_files(dist, cvs):
    cs, en = cvs['cs'], cvs['en']
    (dist / 'index.html').write_text(f'''<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Petr Hýl – CV</title>
<meta name="description" content="{cs['basics']['summary']}">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="alternate" hreflang="cs" href="cs/">
<link rel="alternate" hreflang="en" href="en/">
<link rel="alternate" hreflang="x-default" href="cs/">
<script>
  // Czech and Slovak browsers get the Czech CV, everyone else the English one.
  var l = (navigator.languages || [navigator.language || 'cs']).map(function (x) {{ return x.slice(0, 2); }});
  location.replace(l.indexOf('cs') > -1 || l.indexOf('sk') > -1 ? 'cs/' : 'en/');
</script>
<noscript><meta http-equiv="refresh" content="0; url=cs/"></noscript>
</head>
<body>
<p><a href="cs/" lang="cs">Životopis česky</a> · <a href="en/" lang="en">CV in English</a></p>
</body>
</html>
''')
    def llms_section(cv):
        lang = cv['lang']
        return (f"- [{cv['ui']['docTitle']} (Markdown)]({lang}/cv.md)\n"
                f"- [JSON Resume]({lang}/resume.json)\n"
                f"- [HTML]({lang}/)\n- [PDF]({lang}/{PDF_NAME[lang]})\n")
    (dist / 'llms.txt').write_text(
        f"# {en['basics']['name']}\n\n> {en['basics']['label']}. {en['basics']['summary']}\n\n"
        "The same CV is available in English and Czech. The Markdown and JSON Resume files hold the complete content "
        "and are the best sources for automated reading.\n\n"
        f"## English\n\n{llms_section(en)}\n## Čeština\n\n{llms_section(cs)}")
    base = SITE['url'].rstrip('/')
    (dist / 'robots.txt').write_text('User-agent: *\nAllow: /\n' + (f'Sitemap: {base}/sitemap.xml\n' if base else ''))
    if base:
        urls = ''.join(f'  <url><loc>{base}/{l}/</loc></url>\n' for l in LANGS)
        (dist / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
    (dist / '.nojekyll').write_text('')


def main():
    env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=True)
    env.filters['ym'] = ym
    env.filters['display_url'] = lambda u: re.sub(r'^https?://(www\.)?', '', u).rstrip('/').replace('%C3%BD', 'ý')
    dist, private = ROOT / 'dist', ROOT / 'private'
    for d in (dist, private):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir()
    copy_assets(dist)
    stage = private / '_html'
    stage.mkdir()
    copy_assets(stage)

    cvs = {l: load(l) for l in LANGS}
    jobs = []
    for lang, cv in cvs.items():
        alts = [{'lang': o, 'href': f'../{o}/', 'label': cvs[o]['ui']['langLabel']} for o in LANGS if o != lang]
        pub = dist / lang
        pub.mkdir()
        (pub / 'index.html').write_text(render(env, cv, False, alts, PDF_NAME[lang]))
        (pub / 'cv.md').write_text(markdown(cv, False))
        (pub / 'resume.json').write_text(resume_json(cv))
        jobs.append((pub / 'index.html', pub / PDF_NAME[lang], cv))
        prv = stage / lang
        prv.mkdir()
        (prv / 'index.html').write_text(render(env, cv, True, alts, PDF_NAME[lang]))
        (private / MD_NAME[lang]).write_text(markdown(cv, True))
        jobs.append((prv / 'index.html', private / PDF_NAME[lang], cv))
    root_files(dist, cvs)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for html, pdf, cv in jobs:
            print_pdf(page, html, pdf, cv)
        browser.close()
    shutil.rmtree(stage)
    for html, pdf, _ in jobs:
        print(f'{pdf.relative_to(ROOT)}: {len(PdfReader(str(pdf)).pages)} pages')


if __name__ == '__main__':
    main()

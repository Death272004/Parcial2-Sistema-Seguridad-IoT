#!/usr/bin/env python3
"""Genera docs/guia-paso-a-paso.pdf a partir del Markdown con WeasyPrint.

    python3 docs/generar_pdf.py

Requiere:  pip install markdown weasyprint
"""
import pathlib

import markdown
from weasyprint import HTML

BASE = pathlib.Path(__file__).resolve().parent.parent
DOCS = BASE / "docs"

CSS = """
@page {
  size: A4;
  margin: 2.0cm 1.8cm 2.2cm 1.8cm;
  @top-right {
    content: "Sistema IoT de Seguridad — Guía paso a paso";
    font-family: 'DejaVu Sans', sans-serif;
    font-size: 7.5pt; color: #8b949e;
  }
  @bottom-center {
    content: "Parcial #2 · Desarrollo de Software VIII · UTP  —  página "
             counter(page) " de " counter(pages);
    font-family: 'DejaVu Sans', sans-serif;
    font-size: 7.5pt; color: #8b949e;
  }
}

body {
  font-family: 'DejaVu Sans', Arial, sans-serif;
  font-size: 9.8pt;
  line-height: 1.5;
  color: #1b1f23;
}

h1 {
  font-size: 21pt; color: #0a1117; line-height: 1.25;
  border-bottom: 3px solid #e63946; padding-bottom: 8px;
  margin: 0 0 6px 0;
}
h2 {
  font-size: 13.5pt; color: #0a1117; margin-top: 24px;
  border-left: 5px solid #e63946; padding-left: 9px;
  page-break-after: avoid;
}
h3 {
  font-size: 11pt; color: #333; margin-top: 16px;
  page-break-after: avoid;
}

p { margin: 6px 0; }
li { margin: 2px 0; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 18px 0; }
strong { color: #0a1117; }
a { color: #0969da; text-decoration: none; }

code, pre { font-family: 'DejaVu Sans Mono', 'Courier New', monospace; }
code {
  background-color: #eef1f4; padding: 0 3px;
  font-size: 8.8pt; border-radius: 2px;
}
pre {
  background-color: #f6f8fa; border: 1px solid #d0d7de;
  border-left: 4px solid #e63946; padding: 8px 10px;
  font-size: 7.6pt; line-height: 1.28; white-space: pre-wrap;
  page-break-inside: avoid;
}
pre code { background: none; padding: 0; font-size: inherit; }

table {
  border-collapse: collapse; width: 100%; font-size: 8.6pt;
  margin: 10px 0; page-break-inside: avoid;
}
th {
  background-color: #0a1117; color: #ffffff; padding: 5px 7px;
  text-align: left; border: 1px solid #8b949e;
}
td {
  padding: 4px 7px; border: 1px solid #c9d1d9; vertical-align: top;
}
tr:nth-child(even) td { background-color: #f6f8fa; }

blockquote {
  background-color: #fff8e6; border-left: 4px solid #e0a800;
  margin: 8px 0; padding: 6px 12px;
}
blockquote p { margin: 2px 0; }
"""


def build_html() -> str:
    source = DOCS / "guia-paso-a-paso.md"
    body = markdown.markdown(
        source.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
        output_format="html5",
    )
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Guía paso a paso — Sistema IoT de Seguridad</title>
<style>{css}</style>
</head>
<body>
{body}
<hr>
<p><strong>Parcial #2</strong> · Desarrollo de Software VIII · Universidad
Tecnológica de Panamá · <strong>Richard Rodríguez</strong> ·
github.com/Death272004</p>
</body>
</html>
""".format(css=CSS, body=body)


def main() -> None:
    html = build_html()
    html_out = DOCS / "guia-paso-a-paso.html"
    pdf_out = DOCS / "guia-paso-a-paso.pdf"

    html_out.write_text(html, encoding="utf-8")
    HTML(string=html, base_url=str(BASE)).write_pdf(str(pdf_out))

    print("HTML:", html_out)
    print("PDF :", pdf_out, "|",
          "{:.1f} KB".format(pdf_out.stat().st_size / 1024))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Baut aus allen docs/*.md eine einzelne PDF: docs/ → WM2026_Dokumentation.pdf

Voraussetzungen: pandoc + weasyprint (pip install weasyprint) + System-Libs (pango/cairo).
Aufruf:  python docs/build_pdf.py
"""
import os, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_PDF = os.path.join(ROOT, "WM2026_Dokumentation.pdf")

ORDER = [
    "VISION", "PROJECT_STATUS", "ARCHITECTURE", "ML_MODEL", "MODEL_EXPLANATION",
    "PREDICTION_LOGIC", "MODEL_EVALUATION", "DATA_SOURCES", "DATABASE_SCHEMA",
    "API_SPEC", "BETTING_ENGINE", "LIMITATIONS", "DEPLOYMENT", "DECISIONS",
    "ROADMAP", "RECOVERY",
]

parts = []
for name in ORDER:
    with open(os.path.join(HERE, f"{name}.md"), encoding="utf-8") as f:
        parts.append(f.read().rstrip())
combined_md = os.path.join(HERE, "_combined.md")
with open(combined_md, "w", encoding="utf-8") as f:
    f.write("\n\n".join(parts))

header_html = os.path.join(HERE, "_header.html")
with open(header_html, "w", encoding="utf-8") as f:
    f.write("""<style>
@page { size: A4; margin: 2cm 1.8cm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 9px; color:#999; } }
body { font-family:'DejaVu Sans',sans-serif; font-size:10.5px; line-height:1.5; color:#222; }
h1 { font-size:19px; color:#0a2a5e; border-bottom:2px solid #0a2a5e; padding-bottom:4px;
     page-break-before:always; margin-top:0; }
h1.title { page-break-before:avoid; font-size:30px; text-align:center; margin-top:35%; border:none; }
h2 { font-size:14.5px; color:#16407a; margin-top:1.3em; } h3 { font-size:12px; color:#333; }
code { background:#f3f3f3; padding:1px 3px; border-radius:3px; font-family:'DejaVu Sans Mono',monospace; font-size:9px; }
pre { background:#f6f8fa; border:1px solid #e1e4e8; border-radius:5px; padding:8px; font-size:8.5px; white-space:pre-wrap; word-wrap:break-word; }
pre code { background:none; padding:0; }
table { border-collapse:collapse; width:100%; font-size:9px; margin:0.6em 0; }
th,td { border:1px solid #ccc; padding:3px 6px; text-align:left; vertical-align:top; } th { background:#eef2f8; }
a { color:#16407a; text-decoration:none; } blockquote { border-left:3px solid #cdd; margin-left:0; padding-left:10px; color:#555; }
#TOC { page-break-after:always; } #TOC::before { content:"Inhalt"; font-size:19px; color:#0a2a5e; font-weight:bold; }
#TOC ul { list-style:none; padding-left:0; line-height:1.9; }
</style>""")

html = os.path.join(HERE, "_combined.html")
subprocess.run([
    "pandoc", combined_md, "-o", html,
    "--from=markdown-yaml_metadata_block", "--standalone", "--toc", "--toc-depth=1",
    "--metadata", "title=WM 2026 — Prognose-System · Gesamtdokumentation",
    "--metadata", f"date={datetime.date.today().isoformat()}",
    f"--include-in-header={header_html}",
], check=True)

from weasyprint import HTML
HTML(html).write_pdf(OUT_PDF)
for tmp in (combined_md, header_html, html):
    os.remove(tmp)
print("PDF:", OUT_PDF, "|", round(os.path.getsize(OUT_PDF) / 1024), "KB")

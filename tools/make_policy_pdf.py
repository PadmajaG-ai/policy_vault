"""Render a pack's policy.md to policy.pdf (pandoc for markdown -> HTML, fpdf2 for HTML -> PDF).

Dev-only tool; needs pandoc on PATH and `pip install fpdf2`.
Run:  python tools/make_policy_pdf.py data/inventory
"""
import re
import subprocess
import sys
from pathlib import Path

from fpdf import FPDF

pack = Path(sys.argv[1])
text = (pack / "policy.md").read_text(encoding="utf-8")

# YAML front matter -> title block
meta = {}
m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
if m:
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip('"')
    text = text[m.end():]

html = subprocess.run(["pandoc", "-f", "markdown", "-t", "html"], input=text,
                      capture_output=True, text=True, encoding="utf-8", check=True).stdout
# Core PDF fonts are Latin-1 only
html = html.replace("·", "|").replace("—", "-").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
# fpdf2 tables need explicit widths; give the version-history table sensible ones
html = re.sub(r"<table[^>]*>", '<table width="100%" border="1">', html)
html = re.sub(r"<colgroup>.*?</colgroup>", "", html, flags=re.S)

pdf = FPDF(format="A4")
pdf.set_margins(22, 20, 22)
pdf.add_page()
pdf.set_font("Helvetica", "B", 18)
pdf.multi_cell(0, 9, meta.get("title", ""), new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "", 12)
pdf.multi_cell(0, 7, meta.get("subtitle", "").replace("—", "-"), new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "I", 10)
pdf.multi_cell(0, 6, meta.get("date", ""), new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)
pdf.set_font("Helvetica", "", 10.5)
pdf.write_html(html)
pdf.output(str(pack / "policy.pdf"))
print(f"Wrote {pack / 'policy.pdf'} ({pdf.page_no()} pages)")

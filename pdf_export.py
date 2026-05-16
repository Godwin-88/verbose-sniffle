"""
job_hunter/pdf_export.py

Exports application packages (Markdown → HTML → PDF).
Uses weasyprint if available; falls back to HTML.

Install (optional): pip install weasyprint markdown2
System deps for weasyprint: libpango-1.0 libharfbuzz0b libfontconfig1
  → apt-get install -y libpango-1.0-0 libharfbuzz0 libfontconfig1 (Debian/Ubuntu)
"""

import logging
from typing import Optional, Tuple

log = logging.getLogger(__name__)

_WEASYPRINT_AVAILABLE = False
try:
    import weasyprint
    _WEASYPRINT_AVAILABLE = True
except ImportError:
    pass

_MARKDOWN2_AVAILABLE = False
try:
    import markdown2
    _MARKDOWN2_AVAILABLE = True
except ImportError:
    pass

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
body {
  font-family: 'Inter', Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.6;
  color: #1a1a1a;
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 48px;
}
h1 { font-size: 20pt; border-bottom: 2px solid #1a73e8; padding-bottom: 8px; color: #1a73e8; }
h2 { font-size: 14pt; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; margin-top: 24px; }
h3 { font-size: 12pt; color: #444; }
blockquote { border-left: 4px solid #1a73e8; padding: 8px 16px; margin: 16px 0;
             background: #f8f9ff; color: #444; }
code, pre { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 10pt; }
pre { padding: 12px; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 16px 0; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 10pt; }
th { background: #f0f4ff; font-weight: 600; }
hr { border: none; border-top: 1px solid #e0e0e0; margin: 24px 0; }
a { color: #1a73e8; }
ul, ol { padding-left: 24px; }
li { margin: 4px 0; }
.meta-box { background: #f8f9ff; border: 1px solid #dce8ff; padding: 16px;
            border-radius: 6px; margin-bottom: 24px; }
@page { margin: 20mm 15mm; }
@media print { body { padding: 0; } }
"""


def _md_to_html(markdown_text: str, title: str = "Application Package") -> str:
    if _MARKDOWN2_AVAILABLE:
        body = markdown2.markdown(
            markdown_text,
            extras=["tables", "fenced-code-blocks", "strike", "task_list"]
        )
    else:
        # Minimal fallback — wrap in <pre> for plain text
        escaped = markdown_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = f"<pre style='white-space:pre-wrap'>{escaped}</pre>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <style>{_CSS}</style>
</head>
<body>
  {body}
</body>
</html>"""


def export_to_pdf(markdown_text: str,
                  title: str = "Application Package") -> Tuple[Optional[bytes], str]:
    """
    Convert Markdown to PDF bytes.
    Returns (bytes, "application/pdf") or (html_bytes, "text/html") if weasyprint unavailable.
    """
    html = _md_to_html(markdown_text, title)

    if _WEASYPRINT_AVAILABLE:
        try:
            pdf_bytes = weasyprint.HTML(string=html).write_pdf()
            return pdf_bytes, "application/pdf"
        except Exception as e:
            log.error(f"weasyprint error: {e}")

    log.info("Returning HTML fallback (weasyprint not available)")
    return html.encode("utf-8"), "text/html"


def export_extension() -> str:
    return "pdf" if _WEASYPRINT_AVAILABLE else "html"

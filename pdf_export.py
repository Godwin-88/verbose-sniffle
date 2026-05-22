"""
job_hunter/pdf_export.py

Exports application documents (Markdown → HTML → PDF).
Produces two distinct styled documents:
  • Cover Letter  — clean letterhead, no code blocks
  • Resume/CV     — structured, ATS-friendly layout
"""

import re
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


_CSS_COVER_LETTER = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.7;
  color: #1a1a1a;
  max-width: 780px;
  margin: 0 auto;
  padding: 48px 56px;
}
/* Candidate name as letterhead */
h1 {
  font-size: 22pt;
  font-weight: 700;
  color: #1a1a1a;
  letter-spacing: -0.5px;
  border-bottom: 3px solid #6d28d9;
  padding-bottom: 10px;
  margin-bottom: 4px;
}
/* Contact line + date below name */
h1 + p {
  font-size: 9.5pt;
  color: #555;
  margin-bottom: 28px;
}
hr {
  border: none;
  border-top: 1px solid #e5e5e5;
  margin: 24px 0;
}
/* Recipient / company */
p strong:first-child {
  display: block;
  margin-bottom: 16px;
  font-size: 10.5pt;
}
p { margin-bottom: 14px; }
/* Salutation */
p:has(+ p) { margin-bottom: 10px; }
/* Closing */
strong { font-weight: 600; }
/* Kill any code/pre blocks — should not appear in a cover letter */
pre, code { display: none; }
blockquote { display: none; }
@page { margin: 18mm 14mm; }
"""

_CSS_RESUME = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.6;
  color: #1a1a1a;
  max-width: 780px;
  margin: 0 auto;
  padding: 40px 48px;
}
h1 {
  font-size: 18pt;
  font-weight: 700;
  color: #1a1a1a;
  border-bottom: 3px solid #6d28d9;
  padding-bottom: 8px;
  margin-bottom: 16px;
}
h2 {
  font-size: 12pt;
  font-weight: 700;
  color: #6d28d9;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  border-bottom: 1px solid #e5e5e5;
  padding-bottom: 4px;
  margin-top: 22px;
  margin-bottom: 10px;
}
h3 {
  font-size: 10.5pt;
  font-weight: 600;
  color: #1a1a1a;
  margin-top: 12px;
  margin-bottom: 4px;
}
p { margin-bottom: 8px; }
ul { padding-left: 20px; margin-bottom: 10px; }
li { margin: 3px 0; }
em { font-style: italic; color: #555; font-size: 10pt; }
strong { font-weight: 600; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 9.5pt; }
th { background: #f3f0ff; font-weight: 600; color: #6d28d9; }
hr { border: none; border-top: 1px solid #e5e5e5; margin: 18px 0; }
code {
  background: #f3f0ff;
  color: #6d28d9;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 9pt;
}
pre {
  background: #f8f8f8;
  padding: 10px;
  border-radius: 4px;
  font-size: 9pt;
  white-space: pre-wrap;
}
blockquote {
  border-left: 3px solid #6d28d9;
  padding: 6px 14px;
  margin: 12px 0;
  background: #f8f6ff;
  color: #444;
  font-size: 10pt;
}
@page { margin: 16mm 14mm; }
"""


def _strip_html_comments(md: str) -> str:
    """Remove HTML comments (<!-- ... -->) that WeasyPrint renders as <pre> blocks."""
    return re.sub(r"<!--[\s\S]*?-->", "", md).strip()


def _md_to_html(markdown_text: str, title: str, css: str) -> str:
    clean_md = _strip_html_comments(markdown_text)

    if _MARKDOWN2_AVAILABLE:
        body = markdown2.markdown(
            clean_md,
            extras=["tables", "fenced-code-blocks", "strike", "task_list"]
        )
    else:
        escaped = clean_md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = f"<pre style='white-space:pre-wrap'>{escaped}</pre>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>{css}</style>
</head>
<body>
  {body}
</body>
</html>"""


def _render(html: str) -> Tuple[Optional[bytes], str]:
    if _WEASYPRINT_AVAILABLE:
        try:
            pdf_bytes = weasyprint.HTML(string=html).write_pdf()
            return pdf_bytes, "application/pdf"
        except Exception as e:
            log.error(f"weasyprint error: {e}")
    log.info("Returning HTML fallback (weasyprint unavailable)")
    return html.encode("utf-8"), "text/html"


def export_cover_letter(markdown_text: str, title: str = "Cover Letter") -> Tuple[Optional[bytes], str]:
    """Render the cover letter markdown as a clean professional letter PDF."""
    html = _md_to_html(markdown_text, title, _CSS_COVER_LETTER)
    return _render(html)


def export_resume(markdown_text: str, title: str = "Tailored Resume") -> Tuple[Optional[bytes], str]:
    """Render the resume/tailoring guide markdown as a structured CV PDF."""
    html = _md_to_html(markdown_text, title, _CSS_RESUME)
    return _render(html)


def export_to_pdf(markdown_text: str, title: str = "Application Package") -> Tuple[Optional[bytes], str]:
    """Combined package export (legacy — used for full_doc_md)."""
    html = _md_to_html(markdown_text, title, _CSS_RESUME)
    return _render(html)


def export_extension() -> str:
    return "pdf" if _WEASYPRINT_AVAILABLE else "html"

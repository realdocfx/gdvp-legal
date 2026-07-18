#!/usr/bin/env python3
"""generate_eula.py — Derive EULA.rtf and eula_master.html from LICENSE.md (SSOT).

Usage:
    python scripts/generate_eula.py          # from repo root
    python scripts/generate_eula.py --check  # exit 1 if outputs differ from committed

No external dependencies — stdlib only.
"""
import argparse
import html
import re
import sys
from pathlib import Path

# Self-contained legal SSOT: LICENSE.md is the source; EULA.rtf (installer/app)
# and templates/eula_master.html (server include) are the generated artifacts,
# all inside this repo (gdvp-legal). Consumers vendor it as a submodule.
REPO = Path(__file__).resolve().parent
LICENSE_MD = REPO / "LICENSE.md"
EULA_RTF = REPO / "EULA.rtf"
EULA_HTML = REPO / "templates" / "eula_master.html"


# ---------------------------------------------------------------------------
# Markdown → structured sections
# ---------------------------------------------------------------------------

def parse_license_md(text: str) -> dict:
    """Parse LICENSE.md into a structured dict with metadata + articles."""
    result = {
        "title": "",
        "subtitle": "",
        "effective_date": "",
        "author": "",
        "preamble": "",
        "articles": [],
        "disclaimer": "",
        "footer": "",
    }

    lines = text.split("\n")
    i = 0

    # Title (# heading)
    while i < len(lines):
        m = re.match(r"^#\s+(.+)", lines[i])
        if m:
            result["title"] = m.group(1).strip()
            i += 1
            break
        i += 1

    # Subtitle (## heading)
    while i < len(lines):
        m = re.match(r"^##\s+(.+)", lines[i])
        if m:
            result["subtitle"] = m.group(1).strip()
            i += 1
            break
        if lines[i].strip():
            break
        i += 1

    # Metadata lines (bold key: value)
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        m = re.match(r"\*\*(.+?):\*\*\s*(.*)", line)
        if m:
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            if "date" in key:
                result["effective_date"] = val
            elif "author" in key or "licensor" in key:
                result["author"] = val
            i += 1
        else:
            break

    # Preamble + Articles
    current_article = None
    current_text = []
    preamble_lines = []
    in_preamble = True

    while i < len(lines):
        line = lines[i]

        # Horizontal rule — skip
        if re.match(r"^---\s*$", line):
            i += 1
            continue

        # Article heading (### ARTICLE N. ...)
        m = re.match(r"^###\s+(.+)", line)
        if m:
            heading = m.group(1).strip()
            if in_preamble:
                if "PREAMBLE" in heading.upper():
                    i += 1
                    continue
                # Save preamble
                result["preamble"] = "\n".join(preamble_lines).strip()
                in_preamble = False

            if "PREAMBLE" in heading.upper():
                i += 1
                continue

            # Save previous article
            if current_article is not None:
                current_article["body"] = "\n".join(current_text).strip()
                result["articles"].append(current_article)

            current_article = {"heading": heading, "body": ""}
            current_text = []
            i += 1
            continue

        # Disclaimer detection
        if line.strip().startswith("*DISCLAIMER:"):
            # Save current article
            if current_article is not None:
                current_article["body"] = "\n".join(current_text).strip()
                result["articles"].append(current_article)
                current_article = None
                current_text = []
            # Collect disclaimer
            disc_lines = []
            while i < len(lines) and not re.match(r"^---\s*$", lines[i]) and not lines[i].startswith("**END"):
                disc_lines.append(lines[i])
                i += 1
            result["disclaimer"] = "\n".join(disc_lines).strip().strip("*")
            continue

        # Footer (END OF LICENSE / copyright)
        if line.strip().startswith("**END OF"):
            if current_article is not None:
                current_article["body"] = "\n".join(current_text).strip()
                result["articles"].append(current_article)
                current_article = None
                current_text = []
            footer_lines = []
            while i < len(lines):
                footer_lines.append(lines[i])
                i += 1
            result["footer"] = "\n".join(footer_lines).strip()
            break

        if in_preamble:
            preamble_lines.append(line)
        else:
            current_text.append(line)
        i += 1

    # Flush last article
    if current_article is not None:
        current_article["body"] = "\n".join(current_text).strip()
        result["articles"].append(current_article)

    return result


# ---------------------------------------------------------------------------
# RTF generation
# ---------------------------------------------------------------------------

def rtf_escape(text: str) -> str:
    """Escape special characters for RTF."""
    out = []
    for ch in text:
        cp = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '{':
            out.append('\\{')
        elif ch == '}':
            out.append('\\}')
        elif cp == 0xE7:   # ç
            out.append('\\u231?')
        elif cp == 0xA9:   # ©
            out.append('\\u169?')
        elif cp > 127:
            out.append(f'\\u{cp}?')
        else:
            out.append(ch)
    return "".join(out)


def md_to_rtf_paragraph(text: str) -> str:
    """Convert a markdown paragraph to RTF, handling bold (**) and italic (*)."""
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', lambda m: '{\\b ' + rtf_escape(m.group(1)) + '}', text)
    # Italic: *text*
    text = re.sub(r'\*(.+?)\*', lambda m: '{\\i ' + rtf_escape(m.group(1)) + '}', text)
    # Escape remaining non-bold/italic text parts
    # We need a smarter approach: split by already-processed RTF commands
    # Actually, let's do the escaping first, then apply bold/italic
    return text


def md_paragraph_to_rtf(text: str) -> str:
    """Full pipeline: escape first, then apply formatting."""
    # First escape special RTF chars in non-markdown content
    # Split by bold/italic markers, escape non-marker parts
    parts = []
    # Process bold first
    segments = re.split(r'(\*\*[^*]+\*\*|\*[^*]+\*)', text)
    for seg in segments:
        m_bold = re.match(r'^\*\*(.+)\*\*$', seg)
        m_ital = re.match(r'^\*(.+)\*$', seg)
        if m_bold:
            parts.append('{\\b ' + rtf_escape(m_bold.group(1)) + '}')
        elif m_ital:
            parts.append('{\\i ' + rtf_escape(m_ital.group(1)) + '}')
        else:
            parts.append(rtf_escape(seg))
    return "".join(parts)


def generate_rtf(data: dict) -> str:
    """Generate EULA.rtf from parsed LICENSE.md data."""
    lines = []
    lines.append(r'{\rtf1\ansi\deff0')
    lines.append(r'{\fonttbl{\f0\fswiss\fcharset0 Calibri;}{\f1\fmodern\fcharset0 Courier New;}}')
    lines.append(r'{\colortbl;\red0\green0\blue0;\red51\green51\blue51;\red180\green0\blue0;}')
    lines.append(r'\viewkind4\uc1\pard\sb120\sa120\qc\lang1036')
    lines.append('')

    # Title
    lines.append(r'{\b\fs32 ' + rtf_escape(data["title"]) + r'\par}')
    lines.append(r'{\b\fs26 ' + rtf_escape(data["subtitle"]) + r'\par}')
    lines.append(r'\pard\sb60\sa60\ql')
    lines.append('')

    # Metadata
    lines.append(r'{\b Effective Date:} ' + rtf_escape(data["effective_date"]) + r'\par')
    lines.append(r'{\b Author & Sole Licensor:} ' + rtf_escape(data["author"]) + r'\par')
    lines.append('')

    # Preamble
    lines.append(r'\pard\sb120\sa60\ql{\b\fs24 PREAMBLE\par}')
    lines.append(r'\pard\sb60\sa60\ql\f0\fs20')
    for para in data["preamble"].split("\n\n"):
        para = para.strip()
        if para:
            lines.append(md_paragraph_to_rtf(para) + r'\par')
    lines.append('')

    # Articles
    for article in data["articles"]:
        heading = article["heading"]
        # Strip "ARTICLE N. " prefix variations for cleaner display
        lines.append(r'\pard\sb120\sa60\ql{\b\fs24 ' + rtf_escape(heading) + r'\par}')
        lines.append(r'\pard\sb60\sa60\ql\fs20')

        body = article["body"]
        # Handle numbered lists (1. **Bold:** text)
        paragraphs = body.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # Check for numbered list items
            list_items = re.findall(r'^\d+\.\s+(.+)', para, re.MULTILINE)
            if list_items and len(list_items) > 1:
                for idx, item in enumerate(list_items, 1):
                    lines.append(r'{\pntext ' + str(idx) + r'.\tab}' +
                                 md_paragraph_to_rtf(item.strip()) + r'\par')
            else:
                lines.append(md_paragraph_to_rtf(para) + r'\par')
        lines.append('')

    # Footer
    lines.append(r'\pard\sb120\sa60\qc\fs18\cf2')
    lines.append(r'\u169? 2026 M. Fran\u231?ois-Xavier Briollais. All rights reserved.\par')
    lines.append('}')
    lines.append('')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def md_paragraph_to_html(text: str) -> str:
    """Convert markdown bold/italic to HTML."""
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic: *text*
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


def generate_html(data: dict) -> str:
    """Generate eula_master.html Jinja2 partial from parsed LICENSE.md data."""
    lines = []
    lines.append('<article class="card legal" id="master-license">')
    lines.append(f'  <h1>{html.escape(data["title"])} — {html.escape(data["subtitle"])}</h1>')
    lines.append(f'  <p class="muted"><strong>Effective Date:</strong> {html.escape(data["effective_date"])}</p>')
    lines.append(f'  <p class="muted"><strong>Author &amp; Sole Licensor:</strong> {html.escape(data["author"])}</p>')
    lines.append('')

    # Preamble
    lines.append('  <h2>Preamble</h2>')
    for para in data["preamble"].split("\n\n"):
        para = para.strip()
        if para:
            lines.append(f'  <p>{md_paragraph_to_html(html.escape(para))}</p>')
    lines.append('')

    # Articles
    for article in data["articles"]:
        heading = article["heading"]
        # Clean heading for HTML
        h2_text = html.escape(heading)
        lines.append(f'  <h2>{h2_text}</h2>')

        body = article["body"]
        paragraphs = body.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check for numbered list items
            list_items = re.findall(r'^\d+\.\s+(.+)', para, re.MULTILINE)
            if list_items and len(list_items) > 1:
                lines.append('  <ol>')
                for item in list_items:
                    item_html = md_paragraph_to_html(html.escape(item.strip()))
                    lines.append(f'    <li>{item_html}</li>')
                lines.append('  </ol>')
            else:
                para_html = md_paragraph_to_html(html.escape(para))
                lines.append(f'  <p>{para_html}</p>')
        lines.append('')

    # Footer
    lines.append('  <p class="muted" style="margin-top:2em">&copy; 2026 M. Fran&ccedil;ois-Xavier Briollais. All rights reserved.')
    lines.append('  <br>Full text: <a href="https://github.com/realdocfx/general_digital_voicing_program/blob/main/LICENSE.md">LICENSE.md</a></p>')
    lines.append('</article>')
    lines.append('')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate EULA.rtf and eula_master.html from LICENSE.md")
    parser.add_argument("--check", action="store_true",
                        help="Check mode: exit 1 if generated files differ from committed")
    args = parser.parse_args()

    if not LICENSE_MD.exists():
        print(f"ERROR: {LICENSE_MD} not found", file=sys.stderr)
        sys.exit(1)

    md_text = LICENSE_MD.read_text(encoding="utf-8")
    data = parse_license_md(md_text)

    rtf_content = generate_rtf(data)
    html_content = generate_html(data)

    if args.check:
        # Compare with committed files
        diffs = []
        if EULA_RTF.exists():
            existing = EULA_RTF.read_text(encoding="utf-8")
            if existing.replace("\r\n", "\n") != rtf_content.replace("\r\n", "\n"):
                diffs.append(str(EULA_RTF))
        else:
            diffs.append(f"{EULA_RTF} (missing)")

        if EULA_HTML.exists():
            existing = EULA_HTML.read_text(encoding="utf-8")
            if existing.replace("\r\n", "\n") != html_content.replace("\r\n", "\n"):
                diffs.append(str(EULA_HTML))
        else:
            diffs.append(f"{EULA_HTML} (missing)")

        if diffs:
            print("EULA files are out of date. Run 'python scripts/generate_eula.py' to regenerate:")
            for d in diffs:
                print(f"  - {d}")
            sys.exit(1)
        else:
            print("EULA files are up to date with LICENSE.md")
            sys.exit(0)
    else:
        EULA_RTF.write_text(rtf_content, encoding="utf-8", newline="\n")
        print(f"Generated {EULA_RTF}")

        EULA_HTML.parent.mkdir(parents=True, exist_ok=True)
        EULA_HTML.write_text(html_content, encoding="utf-8", newline="\n")
        print(f"Generated {EULA_HTML}")


if __name__ == "__main__":
    main()

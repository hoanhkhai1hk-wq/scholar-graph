"""Conservative navigation headings; rejected candidates remain in source text."""
import re


def heading_candidate(text):
    text = text.strip()
    return bool(text and len(text) <= 120 and len(text.split()) <= 16
        and not re.search(r'@|https?://|[=∑∗‡]|\b(?:gmail|TFLOPS)\b', text, re.I)
        and not re.search(r'[.;。；]\s|[.!?。！？]$', text))


def post_reference_heading(text):
    """Recover an explicit supplemental heading merged into an image block."""
    first = next((line.strip() for line in text.splitlines() if line.strip()), '')
    if not heading_candidate(first):
        return None
    if re.fullmatch(r'(?:Appendix(?:\s+[A-Z](?:[.:]\s*[^\n]+)?)?|Appendices|'
                    r'Supplementary(?:\s+(?:Material|Materials|Information|Results))?|'
                    r'(?:[A-Z][A-Za-z-]*\s+){0,4}Visualizations)', first):
        return first
    return None

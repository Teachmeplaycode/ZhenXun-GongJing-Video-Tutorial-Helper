"""Export a session as a note: the video info, each Q&A turn (with time points), the cited
keyframes / slow-motion replays / closer-look frames / motion images, and source links.

Markdown bundles its images into a zip (a .md plus an images/ folder); PDF is a print-styled
HTML page the user opens in a browser and prints to PDF — the browser supplies CJK fonts (no
mojibake) and CSS controls paging, with no heavy PDF dependency on the backend.
"""
from .markdown import ImageRef, build_markdown, collect_image_refs, select_messages
from .render import build_print_html, build_zip

__all__ = [
    "ImageRef",
    "build_markdown",
    "build_print_html",
    "build_zip",
    "collect_image_refs",
    "select_messages",
]

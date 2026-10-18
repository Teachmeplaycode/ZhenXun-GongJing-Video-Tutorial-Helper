"""Chapters: a titled table of contents with one-line summaries, built after import.

Splitting is pure (split.py); titles and summaries come from the chat model when one is
available, otherwise from each chapter's transcript text. The result is cached in the job
folder as chapters.json, the same way cuts.json is.
"""
from . import split
from .task import FILE, FINISHED, Chapter, Chapters, load, run_chapters, save

__all__ = ["FILE", "FINISHED", "Chapter", "Chapters", "load", "run_chapters", "save", "split"]

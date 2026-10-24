"""How densely an import samples a video: keyframes, shot fill and the on-screen text rate.

Three presets, chosen on the import screen, plus optional overrides from its "高级" panel:

  quick     32 keyframes, no shot fill, on-screen text every 2 s   short videos, a few quick questions
  standard  48–64 keyframes, a frame for every shot up to 128,     most videos (the default)
            on-screen text every second (every 2 s past LONG_VIDEO)
  fine      64–128 keyframes (about one a second), shot fill up    lectures, blackboard / slides,
            to 256, on-screen text twice a second                    note-taking

More keyframes mostly help browsing the timeline: the agent looks closer on demand (view_frames,
replay), and a question still sends at most LLM_MAX_IMAGES frames. The plan is saved with the session
(video.extra["sampling"]) so a retry reads on-screen text at the same rate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .job import frame_count

MAX_FRAMES = 256
OCR_RATES = (0, 0.5, 1, 2)  # frames per second read for on-screen text; 0 = off
# Past this many seconds the standard preset reads on-screen text every 2 s: on the web demo's 4 cores
# a 20-minute tutorial at one a second took 33 minutes and queued every import behind it; a caption or
# a menu stays up for more than 2 s, and unchanged frames are skipped anyway (modules/screentext/change.py).
LONG_VIDEO = 360


@dataclass
class Plan:
    preset: str
    frames: int       # uniform keyframes
    shots: bool       # add a keyframe for every shot the uniform pass missed
    cap: int          # keyframes in all once shots are filled
    ocr_fps: float    # on-screen text rate; 0 = not read

    def as_dict(self) -> dict:
        return asdict(self)


def _preset(name: str, duration: float) -> Plan:
    if name == "quick":
        return Plan("quick", 32, False, 32, 0.5)
    if name == "fine":
        n = min(128, max(64, round(duration))) if duration > 0 else 64
        return Plan("fine", n, True, MAX_FRAMES, 2)
    return Plan("standard", frame_count(duration), True, 128, 0.5 if duration > LONG_VIDEO else 1)


def plan(spec: dict | None, duration: float) -> Plan:
    """The preset named in `spec` (default standard) with any valid overrides applied:
    frames 8–256, shots true/false, ocr_fps one of OCR_RATES. Anything else is ignored."""
    spec = spec or {}
    p = _preset(str(spec.get("preset") or "standard"), duration)
    try:
        if spec.get("frames") not in (None, ""):
            p.frames = max(8, min(MAX_FRAMES, int(spec["frames"])))
    except (TypeError, ValueError):
        pass
    if isinstance(spec.get("shots"), bool):
        p.shots = spec["shots"]
    try:
        rate = float(spec["ocr_fps"]) if spec.get("ocr_fps") not in (None, "") else None
    except (TypeError, ValueError):
        rate = None
    if rate in OCR_RATES:
        p.ocr_fps = rate
    p.cap = max(p.frames, p.cap) if p.shots else p.frames
    return p


def saved(video) -> dict:
    """The plan a session was imported with (empty for sessions from before presets)."""
    return (getattr(video, "extra", None) or {}).get("sampling") or {}

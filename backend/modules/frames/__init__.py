"""Remote frame sampling with partial-coverage reporting."""
from .grabber import GrabResult, grab_frame
from .job import FrameJob, coarse_first, frame_count

__all__ = ["GrabResult", "grab_frame", "FrameJob", "coarse_first", "frame_count"]

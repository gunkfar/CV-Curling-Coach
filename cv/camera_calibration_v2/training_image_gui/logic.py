"""GUI-independent logic of the training-image tool: validating frames, choosing outputs, running a batch.

All rendering is done by the existing `views.topdown` with a calibration loaded by `cameras.load_camera`; nothing here re-implements lens
correction, the homography or the warp. Source images are only ever read. Outputs are created with exclusive-create ("xb"), so an existing
file can never be overwritten, even by a race.
"""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from ..cameras import load_camera
from ..io import camera_id_from_key
from ..model import CameraCalibration
from ..render import CAMERA_IDS
from ..views import VIEWS, topdown

SUPPORTED_SUFFIXES = (".jpg", ".jpeg", ".png")
EXPECTED_SIZE = (1280, 1024)                                    # (width, height) the calibrations were made for
DEFAULT_VIEW = "wide"
VIEW_NAMES = (DEFAULT_VIEW, *[v for v in VIEWS if v != DEFAULT_VIEW])
MAX_LISTED = 15                                                 # entries shown in a warning before "... and N more"


class ImageRejected(Exception):
    """An input file cannot be used; the message is the reason (without the file name)."""


class CalibrationUnavailable(Exception):
    """The saved calibration for the chosen camera could not be loaded."""


class OutputDirError(Exception):
    """The output directory is unusable."""


# ----------------------------------------------------------------------------------------------------------------- reading input images

def read_image(path) -> np.ndarray:
    """Decode an image file to a BGR array exactly like cv2.imread(path) does, but also for non-ASCII paths on Windows."""
    path = Path(path)
    if path.is_dir():
        raise ImageRejected("it is a folder, not an image file")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ImageRejected(f"unsupported file type {path.suffix or '(no extension)'!r}; supported types are JPG, JPEG and PNG")
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as e:
        raise ImageRejected(f"the file could not be read ({e.strerror or e})") from e
    if data.size == 0:
        raise ImageRejected("the file is empty")
    try:
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    except cv2.error:
        image = None
    if image is None:
        raise ImageRejected("the file could not be decoded as an image (unreadable or corrupt)")
    return image


def load_frame(path) -> np.ndarray:
    """read_image plus the 1280 x 1024 requirement of the calibrations. Used for validation, preview and batch alike."""
    image = read_image(path)
    height, width = image.shape[:2]
    if (width, height) != EXPECTED_SIZE:
        raise ImageRejected(f"expected {EXPECTED_SIZE[0]} × {EXPECTED_SIZE[1]} pixels, received {width} × {height}")
    return image


def _same_file(a, b) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    width: int
    height: int

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class AddResult:
    added: list = field(default_factory=list)          # [ImageInfo]
    rejected: list = field(default_factory=list)       # [(Path, reason)]
    duplicates: list = field(default_factory=list)     # [Path]

    def warning_text(self) -> str:
        """Consolidated, user-readable message about everything that was not added ('' if all were added)."""
        lines = [f"{p.name} was rejected: {reason}." for p, reason in self.rejected]
        lines += [f"{p.name} was skipped: it is already in the list." for p in self.duplicates]
        if len(lines) > MAX_LISTED:
            lines = lines[:MAX_LISTED] + [f"... and {len(lines) - MAX_LISTED} more."]
        return "\n".join(lines)


class ImageSelection:
    """The accepted images, in display order. Every image is validated (fully decoded, size checked) before it enters the list."""

    def __init__(self):
        self.items: list[ImageInfo] = []

    def __len__(self):
        return len(self.items)

    def paths(self) -> list[Path]:
        return [i.path for i in self.items]

    def add(self, paths) -> AddResult:
        result = AddResult()
        for raw in paths:
            path = Path(raw)
            try:
                path = path.resolve()
            except OSError:
                path = path.absolute()
            if any(_same_file(path, i.path) for i in self.items):
                result.duplicates.append(path)
                continue
            try:
                height, width = load_frame(path).shape[:2]          # the pixels are dropped again at once; only the size is kept
            except ImageRejected as e:
                result.rejected.append((path, str(e)))
                continue
            info = ImageInfo(path, width, height)
            self.items.append(info)
            result.added.append(info)
        return result

    def remove(self, indices) -> None:
        drop = set(indices)
        self.items = [i for n, i in enumerate(self.items) if n not in drop]

    def clear(self) -> None:
        self.items = []


# ------------------------------------------------------------------------------------------------------------------- camera / calibration

def camera_name(camera_id: int) -> str:
    if isinstance(camera_id, bool) or camera_id not in CAMERA_IDS:
        raise ValueError(f"camera_id must be an integer from 1 to 12, got {camera_id!r}")
    return f"camera{camera_id}"


def load_calibration_for(camera_id: int) -> CameraCalibration:
    """The saved calibration of camera `camera_id` (via cameras.load_camera); raises CalibrationUnavailable with a readable reason."""
    name = camera_name(camera_id)
    try:
        cal = load_camera(name)
    except Exception as e:                                                    # missing file, bad JSON, schema errors, ...
        raise CalibrationUnavailable(f"The calibration for {name} could not be loaded: {type(e).__name__}: {e}") from e
    if cal.camera_id != name:
        raise CalibrationUnavailable(f"The calibration file loaded for {name} is labelled {cal.camera_id!r}.")
    return cal


def calibration_warning(cal: CameraCalibration) -> str:
    """Text for a non-blocking notice when the calibration is not verified ('' if it is)."""
    if cal.provenance.get("verified"):
        return ""
    return (f"{cal.camera_id} calibration is UNVERIFIED: its accuracy was checked against painted sheet geometry only, "
            f"not against measured stone positions.")


def filename_camera_mismatches(paths, camera_id: int) -> list[tuple[str, str]]:
    """[(file name, camera named in it)] for files whose name starts with a different 'cameraN_' than the selected camera."""
    expected = camera_name(camera_id)
    out = []
    for p in paths:
        try:
            named = camera_id_from_key(str(p))
        except ValueError:
            continue                                                         # no camera in the name: nothing to compare
        if named != expected:
            out.append((Path(p).name, named))
    return out


# --------------------------------------------------------------------------------------------------------------------------- output files

class DirState(enum.Enum):
    EMPTY = "empty"
    OK = "ok"
    MISSING = "missing"
    NOT_A_DIRECTORY = "not_a_directory"


def output_dir_state(text) -> DirState:
    text = str(text).strip()
    if not text:
        return DirState.EMPTY
    path = Path(text).expanduser()
    if path.is_dir():
        return DirState.OK
    if path.exists():
        return DirState.NOT_A_DIRECTORY
    return DirState.MISSING


def ensure_output_dir(text) -> Path:
    """The output directory as a Path; created (with parents) only if it does not exist. Raises OutputDirError."""
    state = output_dir_state(text)
    if state is DirState.EMPTY:
        raise OutputDirError("No output directory was chosen.")
    path = Path(str(text).strip()).expanduser()
    if state is DirState.NOT_A_DIRECTORY:
        raise OutputDirError(f"{path} exists but is not a folder.")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OutputDirError(f"The output folder {path} could not be created: {e.strerror or e}") from e
    return path


def output_name(source, camera_id: int, view: str) -> str:
    """'camera6_20260519_154543.jpg', 6, 'wide' -> 'camera6_20260519_154543_camera6_wide.png'."""
    return f"{Path(source).stem}_{camera_name(camera_id)}_{view}.png"


def write_png_exclusive(image: np.ndarray, path) -> None:
    """Write `image` as a lossless PNG at `path`; raises FileExistsError (and writes nothing) if the path already exists."""
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise OSError("PNG encoding failed")
    path = Path(path)
    f = open(path, "xb")                                                       # exclusive create: never overwrites
    try:
        with f:
            f.write(buf.tobytes())
    except BaseException:
        path.unlink(missing_ok=True)                                           # a partial file that this call created
        raise


# ----------------------------------------------------------------------------------------------------------------------------- rendering

def render_image(cal: CameraCalibration, image: np.ndarray, view: str) -> np.ndarray:
    """Top-down image of one frame: exactly render_topdown / render_batch, but with an already loaded calibration."""
    if view not in VIEWS:
        raise ValueError(f"view must be one of {list(VIEWS)}, got {view!r}")
    out, _ = topdown(cal, image, view)
    return out


def render_preview(path, camera_id: int, view: str, cal: CameraCalibration | None = None) -> np.ndarray:
    """Top-down image of the file at `path` for the preview; nothing is saved. Raises ImageRejected / CalibrationUnavailable."""
    image = load_frame(path)
    return render_image(load_calibration_for(camera_id) if cal is None else cal, image, view)


# --------------------------------------------------------------------------------------------------------------------------------- batch

OK, FAILED, SKIPPED = "ok", "failed", "skipped"


@dataclass
class ItemResult:
    source: Path
    status: str                          # OK | FAILED | SKIPPED
    message: str = ""
    output: Path | None = None


@dataclass
class BatchSummary:
    results: list = field(default_factory=list)
    total: int = 0
    cancelled: bool = False

    def _count(self, status):
        return sum(r.status == status for r in self.results)

    @property
    def succeeded(self):
        return self._count(OK)

    @property
    def failed(self):
        return self._count(FAILED)

    @property
    def skipped(self):
        return self._count(SKIPPED)

    @property
    def not_processed(self):
        return self.total - len(self.results)

    def text(self) -> str:
        head = f"{self.succeeded} succeeded, {self.failed} failed, {self.skipped} skipped"
        if self.cancelled:
            head += f"; cancelled with {self.not_processed} image(s) not processed"
        problems = [f"{r.source.name}: {r.message}" for r in self.results if r.status != OK]
        if len(problems) > MAX_LISTED:
            problems = problems[:MAX_LISTED] + [f"... and {len(problems) - MAX_LISTED} more (see the log)."]
        return head + ("\n\n" + "\n".join(problems) if problems else "")


def _process_one(cal, source: Path, out_dir: Path, camera_id: int, view: str) -> ItemResult:
    dest = out_dir / output_name(source, camera_id, view)
    if dest.exists():
        return ItemResult(source, SKIPPED, f"output file {dest.name} already exists; it was not overwritten", dest)
    try:
        image = load_frame(source)
        rendered = render_image(cal, image, view)
        del image                                                              # only one full frame in memory at a time
        write_png_exclusive(rendered, dest)
    except FileExistsError:
        return ItemResult(source, SKIPPED, f"output file {dest.name} already exists; it was not overwritten", dest)
    except ImageRejected as e:
        return ItemResult(source, FAILED, str(e))
    except Exception as e:                                                     # keep going with the other images
        return ItemResult(source, FAILED, f"{type(e).__name__}: {e}")
    return ItemResult(source, OK, "", dest)


def run_batch(paths, camera_id: int, view: str, out_dir, on_progress=None, should_cancel=None,
              cal: CameraCalibration | None = None) -> BatchSummary:
    """Transform `paths` (in order) with one camera calibration and view, saving PNGs in `out_dir` (which must exist).

    on_progress(done, total, ItemResult) is called after every image; should_cancel() is checked between images only.
    A failing image is recorded and the batch continues. Existing outputs are skipped, never overwritten.
    """
    paths = [Path(p) for p in paths]
    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        raise OutputDirError(f"The output folder {out_dir} does not exist.")
    if view not in VIEWS:
        raise ValueError(f"view must be one of {list(VIEWS)}, got {view!r}")
    cal = load_calibration_for(camera_id) if cal is None else cal               # once per batch
    summary = BatchSummary(total=len(paths))
    for source in paths:
        if should_cancel is not None and should_cancel():
            summary.cancelled = True
            break
        result = _process_one(cal, source, out_dir, camera_id, view)
        summary.results.append(result)
        if on_progress is not None:
            on_progress(len(summary.results), summary.total, result)
    return summary

"""Shared pytest configuration for the test suite.

Ensures the project source root (``src/``, which contains the ``config``
package) is on ``sys.path`` so tests can import ``config.inspector`` and
``app`` regardless of where pytest is invoked from. Also defines reusable
image fixtures shared across test modules.

No heavy library (torch/cv2/pyzbar/PIL) is imported at module scope — tests
that need them use ``pytest.importorskip`` and keep passing (via *skip*)
when the dependency is not installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------
# sys.path: project source root = src/ (the folder that contains the
# `config` and `app` packages).
# conftest.py lives at src/tests/conftest.py -> parents[1] == src/.
# --------------------------------------------------------------------------
SRC_ROOT = Path(__file__).resolve().parents[1]          # .../src
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Synthetic dataset test-split directory (relative to the project source
# root: src/config/datasets/...).
_TEST_DIR = SRC_ROOT / "config" / "datasets" / "dataset_sintetico" / "images" / "test"


@pytest.fixture
def test_image() -> Path:
    """Return the path of the first ``.png`` in the synthetic dataset's test split.

    Searches recursively under ``config/datasets/dataset_sintetico/images/test/**``.

    Returns:
        Path: absolute path to the first ``.png`` file found (sorted order).

    Side effects:
        None; this fixture only reads the filesystem.

    Failure modes:
        If the dataset directory is missing, or it exists but contains no
        ``.png`` files, the test using this fixture is *skipped* (via
        ``pytest.skip``) instead of failing, since the dataset is a large
        external asset that may not be present in every environment.
    """
    if not _TEST_DIR.exists():
        pytest.skip(f"missing test dataset: {_TEST_DIR}")
    pngs = sorted(_TEST_DIR.glob("**/*.png"))
    if not pngs:
        pytest.skip(f"no .png files found in {_TEST_DIR}")
    return pngs[0]


@pytest.fixture
def tmp_image(tmp_path) -> Path:
    """Create a small PNG with PIL under ``tmp_path`` and return its path.

    Args:
        tmp_path: built-in pytest fixture providing a unique temporary
            directory for the test invocation.

    Returns:
        Path: path to the newly created 32x16 white PNG image.

    Side effects:
        Writes a single image file to ``tmp_path``.

    Failure modes:
        Requires Pillow; if it is not installed, the test using this
        fixture is *skipped* (via ``pytest.importorskip``).
    """
    Image = pytest.importorskip("PIL.Image")
    path = tmp_path / "sample.png"
    img = Image.new("RGB", (32, 16), color=(255, 255, 255))
    img.save(path)
    return path

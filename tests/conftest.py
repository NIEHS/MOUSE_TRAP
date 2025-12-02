import os
import pytest

# Prefer headless Qt. Fall back to a minimal plugin if needed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """A QApplication for tests that touch Qt widgets."""
    app = QApplication.instance()
    if app is None:
        try:
            app = QApplication([])
        except Exception:
            # Some systems may not have 'offscreen'; try a minimal plugin.
            os.environ["QT_QPA_PLATFORM"] = "minimal"
            app = QApplication([])
    return app

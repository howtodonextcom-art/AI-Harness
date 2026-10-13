"""XAU EDGE: probabilistic decision-support research platform for XAUUSD."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("xau-edge")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0+unknown"

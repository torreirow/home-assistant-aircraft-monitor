"""Test bootstrap.

The integration package's ``__init__.py`` imports Home Assistant, which is not
a dependency of the pure-logic test suite. To test ``geo``/``api``/``processing``
in isolation we register a lightweight package object for ``aircraft_monitor``
that points at the source directory *without* executing the real package
``__init__``. Relative imports inside the submodules then resolve normally.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "custom_components" / "aircraft_monitor"

if "aircraft_monitor" not in sys.modules:
    _pkg = types.ModuleType("aircraft_monitor")
    _pkg.__path__ = [str(_SRC)]  # type: ignore[attr-defined]
    sys.modules["aircraft_monitor"] = _pkg

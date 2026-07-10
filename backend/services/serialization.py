"""
Turning engine outputs into clean JSON.

THE PROBLEM
-----------
Our engines return rich Python objects: dataclasses that contain enums, numpy
numbers (np.float64, np.int64), numpy arrays, and — importantly — NaN / inf
values from pandas. If we hand those straight to FastAPI, two things break:

  1. numpy types aren't JSON-serializable by default.
  2. NaN / Infinity are not valid JSON (they produce literal `NaN` tokens that
     browsers and strict parsers reject).

THE SOLUTION
------------
One recursive function, `to_jsonable`, that walks any object and converts it
into primitives the standard `json` module (and FastAPI) fully understands:
plain dicts, lists, str, int, float, bool, None. NaN/inf become None.

Keeping this in one file means every engine's output is serialized the same
way, so the API stays consistent no matter which engine produced the data.
"""

from __future__ import annotations

import dataclasses
import math
from enum import Enum
from typing import Any

import numpy as np


def to_jsonable(obj: Any) -> Any:
    """Recursively convert `obj` into JSON-safe primitives.

    Handles: dataclasses, enums, numpy scalars/arrays, sets/tuples, dicts,
    lists, and the NaN/inf floats that pandas loves to produce.
    """
    # --- None and plain strings/bools pass straight through ---------------
    # (bool must be checked before int, since bool is a subclass of int)
    if obj is None or isinstance(obj, (str, bool)):
        return obj

    # --- Enums: use their value (all our enums are str-valued) ------------
    if isinstance(obj, Enum):
        return obj.value

    # --- Dataclass instances: convert to a dict, then recurse -------------
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}

    # --- numpy scalar types ----------------------------------------------
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return _clean_float(float(obj))
    if isinstance(obj, np.bool_):
        return bool(obj)

    # --- numpy arrays -> lists -------------------------------------------
    if isinstance(obj, np.ndarray):
        return [to_jsonable(x) for x in obj.tolist()]

    # --- native floats: scrub NaN / inf ----------------------------------
    if isinstance(obj, float):
        return _clean_float(obj)

    # --- native ints -----------------------------------------------------
    if isinstance(obj, int):
        return obj

    # --- mappings --------------------------------------------------------
    if isinstance(obj, dict):
        # JSON keys must be strings.
        return {str(k): to_jsonable(v) for k, v in obj.items()}

    # --- sequences / sets ------------------------------------------------
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(x) for x in obj]

    # --- fallback: last-resort string ------------------------------------
    # Reaching here means an unexpected type slipped through; stringifying is
    # safer than crashing the whole response.
    return str(obj)


def _clean_float(x: float) -> float | None:
    """NaN and +/-inf are invalid JSON. Represent them as null instead."""
    if math.isnan(x) or math.isinf(x):
        return None
    return x

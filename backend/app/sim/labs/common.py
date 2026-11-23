"""Shared helpers for the concept labs. Every lab is deterministic, so the server can replay a player's settings."""
from __future__ import annotations

from typing import Any, Dict, List

from ..builder import mulberry32  # noqa: F401  (re-exported for the labs)


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    k = max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))
    return float(xs[k])


def clean_settings(controls: List[Dict[str, Any]], raw: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only known controls, and force every value into its allowed range."""
    raw = raw if isinstance(raw, dict) else {}
    out: Dict[str, Any] = {}
    for c in controls:
        v = raw.get(c["id"], c["default"])
        t = c["type"]
        if t == "select":
            ok = {o[0] for o in c["options"]}
            out[c["id"]] = v if v in ok else c["default"]
        elif t == "range":
            try:
                n = float(v)
            except (TypeError, ValueError):
                n = float(c["default"])
            step = c.get("step", 1)
            n = max(c["min"], min(c["max"], round(n / step) * step))
            out[c["id"]] = int(n) if float(step).is_integer() else round(n, 3)
        elif t == "toggle":
            out[c["id"]] = bool(v)
        elif t == "multi":
            ok = {o[0] for o in c["options"]}
            seen: List[str] = []
            for x in (v if isinstance(v, list) else []):
                if x in ok and x not in seen:
                    seen.append(x)
            out[c["id"]] = seen[: c.get("max", len(ok))]
        else:
            out[c["id"]] = c["default"]
    return out


def sel(id_: str, label: str, options: List[List[str]], default: str, help_: str = "") -> Dict[str, Any]:
    return {"id": id_, "label": label, "type": "select", "options": options, "default": default, "help": help_}


def rng(id_: str, label: str, lo: float, hi: float, step: float, default: float, help_: str = "", unit: str = "") -> Dict[str, Any]:
    return {"id": id_, "label": label, "type": "range", "min": lo, "max": hi, "step": step, "default": default, "help": help_, "unit": unit}


def tog(id_: str, label: str, default: bool = False, help_: str = "") -> Dict[str, Any]:
    return {"id": id_, "label": label, "type": "toggle", "default": default, "help": help_}

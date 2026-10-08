
"""Decision Capital | Treasury Relative Value Engine.

Inputs: rates.json (public Treasury curve feed).
Output: data/relative_value.json (separate research file).

All yields are in percent. Spreads and butterflies are in basis points.
"""
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev

TENORS = (2, 3, 5, 7, 10, 20, 30)
SPREADS = {
    "2s10s": (2, 10),
    "5s30s": (5, 30),
    "10s30s": (10, 30),
}
FLIES = {
    "2s5s10s": (2, 5, 10),
    "5s10s30s": (5, 10, 30),
    "10s20s30s": (10, 20, 30),
}
WINDOWS = (20, 60, 125, 252)


def valid_yield(value):
    """Return a valid finite yield or None."""
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def extract_curve(record):
    """Normalize a historical row or current curve to tenor -> yield."""
    if "curve" in record:
        values = {
            item["tenor"]: item["yield"]
            for item in record["curve"]
            if "tenor" in item and "yield" in item
        }
    else:
        values = record

    result = {}
    for tenor in TENORS:
        value = valid_yield(values.get(f"{tenor}Y"))
        if value is not None:
            result[tenor] = value
    return result


def calculate_metrics(curve):
    """Calculate curve spreads and maturity-weighted butterflies."""
    result = {}

    for name, (short, long) in SPREADS.items():
        if short in curve and long in curve:
            result[name] = round(
                100 * (curve[long] - curve[short]), 4
            )

    for name, (left, belly, right) in FLIES.items():
        if all(t in curve for t in (left, belly, right)):
            left_weight = (right - belly) / (right - left)
            right_weight = (belly - left) / (right - left)
            theoretical = (
                left_weight * curve[left]
                + right_weight * curve[right]
            )
            result[name] = round(
                100 * (curve[belly] - theoretical), 4
            )

    return result


def historical_stats(current, observations):
    """Calculate statistics using preceding observations only."""
    result = {}

    for window in WINDOWS:
        sample = observations[-window:]
        # Require a complete lookback window.
        if len(sample) < window:
            result[str(window)] = None
            continue

        avg = mean(sample)
        sd = pstdev(sample)

        result[str(window)] = {
            "mean_bp": round(avg, 4),
            "std_bp": round(sd, 4),
            "z_score": round((current - avg) / sd, 4)
            if sd > 0 else None,
            "percentile": round(
                100 * (
                    sum(x < current for x in sample)
                    + 0.5 * sum(x == current for x in sample)
                ) / len(sample),
                2,
            ),
            "observations": len(sample),
        }

    return result


def main():
    source = Path("rates.json")
    output = Path("data/relative_value.json")

    raw = json.loads(source.read_text(encoding="utf-8"))
    as_of = raw["updated"]
    datetime.strptime(as_of, "%Y-%m-%d")

    # The latest observation comes from the current curve.
    current_curve = extract_curve(raw)
    current_metrics = calculate_metrics(current_curve)

    # Keep only historical rows strictly before the current date.
    history = {}
    for row in raw.get("history", []):
        date = row.get("date")
        if not date or date >= as_of:
            continue
        datetime.strptime(date, "%Y-%m-%d")
        if date in history:
            raise ValueError(f"Duplicate historical date: {date}")
        history[date] = calculate_metrics(extract_curve(row))

    sorted_dates = sorted(history)

    result = {
        "as_of": as_of,
        "source": "Decision Capital rates.json / U.S. Treasury",
        "units": "basis_points",
        "methodology": {
            "spreads": "Long yield minus short yield",
            "butterflies": "Belly yield minus maturity-weighted linear interpolation of wings",
            "statistics": "Prior observations only; complete windows required",
            "limitations": (
                "Tenor-level diagnostics, not individual bond valuations. "
                "Maturity-weighted flies are not DV01-neutral. "
                "Missing historical tenors do not receive estimated yields."
            ),
        },
        "metrics": {},
    }

    for name, current in current_metrics.items():
        observations = [
            history[date][name]
            for date in sorted_dates
            if name in history[date]
        ]
        result["metrics"][name] = {
            "value_bp": current,
            "statistics": historical_stats(current, observations),
            "history_count": len(observations),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Relative value data generated: {output}")


if __name__ == "__main__":
    main()

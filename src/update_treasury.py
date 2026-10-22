"""Update the public Treasury feed from official Daily Treasury Par Yield Curve CSV."""
import csv
import io
import json
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path("rates.json")
LABELS = {
    "1M": "1 Mo", "1.5M": "1.5 Mo", "2M": "2 Mo",
    "3M": "3 Mo", "4M": "4 Mo", "6M": "6 Mo",
    "1Y": "1 Yr", "2Y": "2 Yr", "3Y": "3 Yr",
    "5Y": "5 Yr", "7Y": "7 Yr", "10Y": "10 Yr",
    "20Y": "20 Yr", "30Y": "30 Yr",
}
YEAR = datetime.now().year
URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    f"interest-rates/daily-treasury-rates.csv/{YEAR}/all"
    f"?type=daily_treasury_yield_curve&field_tdr_date_value={YEAR}"
    "&_format=csv"
)


def spread(yields, short, long):
    return round((yields[long] - yields[short]) * 100, 2)


def main():
    current = json.loads(ROOT.read_text(encoding="utf-8"))
    req = urllib.request.Request(
        URL, headers={"User-Agent": "DecisionCapitalResearch/1.0"}
    )
    with urllib.request.urlopen(req, timeout=35) as response:
        content = response.read().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(content)))
    if not rows or "Date" not in rows[0]:
        raise ValueError("Treasury CSV missing Date field")
    available = []
    for row in rows:
        try:
            day = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date()
            yields = {
                tenor: float(row[column].strip())
                for tenor, column in LABELS.items()
            }
            if not all(0 < value < 30 for value in yields.values()):
                raise ValueError("Implausible Treasury yields")
            available.append((day.isoformat(), yields))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    if not available:
        raise ValueError("No complete dated Treasury curve found")
    day, yields = max(available, key=lambda x: x[0])
    if day < current["updated"]:
        raise ValueError("Official source older than existing data")
    if day == current["updated"] and all(
        float(p["yield"]) == yields[p["tenor"]]
        for p in current["curve"]
    ):
        print("Already current:", day)
        return

    history = current["history"]
    previous = history[-1] if day > current["updated"] else history[-2]
    spreads = {
        "2s10s_bp": spread(yields, "2Y", "10Y"),
        "5s30s_bp": spread(yields, "5Y", "30Y"),
        "2s30s_bp": spread(yields, "2Y", "30Y"),
    }
    for item in current["curve"]:
        item["yield"] = yields[item["tenor"]]
    for tenor in ("2Y", "5Y", "10Y", "30Y"):
        current["benchmarks"][tenor] = {
            "yield": yields[tenor],
            "change_bp": round(100 * (yields[tenor] - previous[tenor]), 2),
        }
    for name, value in spreads.items():
        current["spreads"][name] = value
        current["spreads"][name.replace("_bp", "_change_bp")] = round(
            value - previous[name], 2
        )
    observation = {
        "date": day,
        **{tenor: yields[tenor] for tenor in ("2Y", "5Y", "10Y", "30Y")},
        **spreads,
    }
    history = [item for item in history if item["date"] != day]
    history.append(observation)
    history.sort(key=lambda x: x["date"])
    current["history"] = history[-500:]
    current["updated"] = day
    ROOT.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    print("Updated Treasury feed:", day)


if __name__ == "__main__":
    main()

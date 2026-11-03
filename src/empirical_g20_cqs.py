#!/usr/bin/env python3
"""
Reproducible G20 panel example for cyclic quotient systems.

Paper focus
-----------
This script downloads World Bank indicators for the 19 G20 member countries
that are sovereign states (the EU and African Union are excluded), constructs
population density and inequality measures, checks the exact population-area-Gini
quotient identity, and estimates a descriptive two-way fixed-effects association
between inequality, density, and real GDP per capita.

Important interpretation
------------------------
The quotient product computed from one common country-year vector is exactly
one by construction. It is not a noisy-cycle test and provides no independent
empirical result. A test of noisy cycle closure requires separately measured
edge log-ratios and their joint sampling/measurement-error covariance. The
World Bank level indicators downloaded here do not provide such independent
edge estimates. The panel regression is a separate descriptive exercise; it
is not causal without additional identification assumptions.

Install dependencies with:
    python -m pip install pandas requests statsmodels numpy

Run:
    python empirical_g20_cqs.py --start 2000 --end 2023 --output-dir ../outputs

Data source: World Bank Indicators API, https://api.worldbank.org/
Indicators:
    SP.POP.TOTL       Population, total
    AG.LND.TOTL.K2    Land area (sq. km)
    SI.POV.GINI       Gini index (World Bank definition / reported scale)
    NY.GDP.PCAP.KD    GDP per capita (constant 2015 US$)
"""

from __future__ import annotations

import argparse
import logging
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import statsmodels.formula.api as smf

LOGGER = logging.getLogger("g20_cqs")
BASE_URL = "https://api.worldbank.org/v2"

# G20 country members, ISO 3166-1 alpha-3 codes.
# The EU and African Union are excluded because this is a country panel.
G20_COUNTRIES = {
    "ARG": "Argentina",
    "AUS": "Australia",
    "BRA": "Brazil",
    "CAN": "Canada",
    "CHN": "China",
    "FRA": "France",
    "DEU": "Germany",
    "IND": "India",
    "IDN": "Indonesia",
    "ITA": "Italy",
    "JPN": "Japan",
    "KOR": "Korea, Rep.",
    "MEX": "Mexico",
    "RUS": "Russian Federation",
    "SAU": "Saudi Arabia",
    "ZAF": "South Africa",
    "TUR": "Turkiye",
    "GBR": "United Kingdom",
    "USA": "United States",
}

INDICATORS = {
    "population": "SP.POP.TOTL",
    "land_area_km2": "AG.LND.TOTL.K2",
    "gini": "SI.POV.GINI",
    "gdp_per_capita": "NY.GDP.PCAP.KD",
}


def fetch_indicator(
    session: requests.Session,
    indicator: str,
    start_year: int,
    end_year: int,
    retries: int = 4,
) -> pd.DataFrame:
    """Fetch one World Bank indicator for the selected G20 country codes."""
    country_path = ";".join(G20_COUNTRIES)
    url = f"{BASE_URL}/country/{country_path}/indicator/{indicator}"
    params = {
        "format": "json",
        "per_page": 20000,
        "date": f"{start_year}:{end_year}",
    }

    for attempt in range(retries):
        try:
            response = session.get(url, params=params, timeout=60)
            response.raise_for_status()
            payload: Any = response.json()
            if not isinstance(payload, list) or len(payload) < 2:
                raise ValueError(f"Unexpected World Bank response for {indicator}: {payload!r}")

            rows = payload[1] or []
            records = []
            for row in rows:
                if row.get("countryiso3code") not in G20_COUNTRIES:
                    continue
                records.append(
                    {
                        "iso3": row["countryiso3code"],
                        "year": int(row["date"]),
                        "value": row.get("value"),
                    }
                )
            frame = pd.DataFrame(records, columns=["iso3", "year", "value"])
            if frame.empty:
                LOGGER.warning("No observations returned for World Bank indicator %s", indicator)
            return frame.rename(columns={"value": indicator})
        except (requests.RequestException, ValueError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(f"Failed to retrieve {indicator} after {retries} attempts") from exc
            wait = 2 ** attempt
            LOGGER.warning("Fetch failed for %s (%s); retrying in %s seconds", indicator, exc, wait)
            time.sleep(wait)

    raise AssertionError("Unreachable retry loop")


def download_panel(start_year: int, end_year: int) -> pd.DataFrame:
    """Download and merge the indicator series into a country-year panel."""
    session = requests.Session()
    session.headers.update({"User-Agent": "CyclicQuotientSystems-empirical-example/1.0"})

    panel: pd.DataFrame | None = None
    for name, indicator in INDICATORS.items():
        LOGGER.info("Downloading %s (%s)", name, indicator)
        series = fetch_indicator(session, indicator, start_year, end_year)
        series = series.rename(columns={indicator: name})
        panel = series if panel is None else panel.merge(series, on=["iso3", "year"], how="outer")

    if panel is None or panel.empty:
        raise RuntimeError("The World Bank API returned no usable panel observations")

    panel["country"] = panel["iso3"].map(G20_COUNTRIES)
    panel["year"] = panel["year"].astype(int)
    for name in INDICATORS:
        panel[name] = pd.to_numeric(panel[name], errors="coerce")

    return panel.sort_values(["iso3", "year"]).reset_index(drop=True)


def construct_measures(panel: pd.DataFrame) -> pd.DataFrame:
    """Create density, log variables, and the algebraic level-cycle check."""
    result = panel.copy()
    result["population_density"] = result["population"] / result["land_area_km2"]

    valid = (
        (result["population"] > 0)
        & (result["land_area_km2"] > 0)
        & (result["gini"] > 0)
        & (result["gdp_per_capita"] > 0)
        & (result["population_density"] > 0)
    )

    # Important: initialize as float columns, not pandas NA object columns.
    result["log_gini"] = float("nan")
    result["log_density"] = float("nan")
    result["log_gdp_per_capita"] = float("nan")

    result.loc[valid, "log_gini"] = result.loc[valid, "gini"].astype(float).map(np.log)
    result.loc[valid, "log_density"] = result.loc[valid, "population_density"].astype(float).map(np.log)
    result.loc[valid, "log_gdp_per_capita"] = result.loc[valid, "gdp_per_capita"].astype(float).map(np.log)

    cycle_valid = (
        (result["population"] > 0)
        & (result["land_area_km2"] > 0)
        & (result["gini"] > 0)
    )

    result["level_cycle_product"] = float("nan")
    result.loc[cycle_valid, "level_cycle_product"] = (
        result.loc[cycle_valid, "population"]
        / result.loc[cycle_valid, "land_area_km2"]
        * result.loc[cycle_valid, "land_area_km2"]
        / result.loc[cycle_valid, "gini"]
        * result.loc[cycle_valid, "gini"]
        / result.loc[cycle_valid, "population"]
    )

    return result


def fit_descriptive_panel_model(panel: pd.DataFrame, output_dir: Path) -> str:
    """Fit a descriptive two-way fixed-effects model with country-clustered standard errors."""
    numeric_columns = ["log_gini", "log_density", "log_gdp_per_capita"]
    for column in numeric_columns:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")

    model_data = panel.dropna(subset=numeric_columns + ["iso3", "year"]).copy()
    model_data["year"] = model_data["year"].astype(int)

    n_countries = model_data["iso3"].nunique()
    n_years = model_data["year"].nunique()
    if len(model_data) < 30 or n_countries < 3 or n_years < 3:
        raise RuntimeError(
            "Too few complete observations for the illustrative panel model: "
            f"N={len(model_data)}, countries={n_countries}, years={n_years}. "
            "Consider a different period or outcome, and document any change."
        )

    formula = "log_gini ~ log_density + log_gdp_per_capita + C(iso3) + C(year)"
    fitted = smf.ols(formula, data=model_data).fit(
        cov_type="cluster",
        cov_kwds={"groups": model_data["iso3"], "use_correction": True},
    )

    note = (
        "Descriptive two-way fixed-effects association. Coefficients are not "
        "causal without a defensible identification strategy. Gini observations "
        "are sparse and may be non-randomly missing. Cluster-robust inference "
        f"uses only {n_countries} country clusters; conventional cluster "
        "asymptotics may be unreliable with so few clusters."
    )

    text = (
        f"Model: {formula}\n"
        f"Observations: {int(fitted.nobs)}\n"
        f"Countries: {n_countries}\n"
        f"Years: {n_years}\n\n"
        f"Interpretation note: {note}\n\n"
        f"{fitted.summary()}\n"
    )
    (output_dir / "panel_model.txt").write_text(text, encoding="utf-8")
    return text


def make_summary(panel: pd.DataFrame, output_dir: Path, start_year: int, end_year: int) -> None:
    """Write data coverage, descriptive statistics, and cycle check outputs."""
    analysis_vars = ["population_density", "gini", "gdp_per_capita"]
    desc = panel[analysis_vars].describe().T
    desc.to_csv(output_dir / "descriptive_statistics.csv")

    coverage = (
        panel.groupby("iso3", as_index=False)
        .agg(
            country=("country", "first"),
            panel_years=("year", "nunique"),
            gini_observations=("gini", "count"),
            population_observations=("population", "count"),
            area_observations=("land_area_km2", "count"),
            gdp_pc_observations=("gdp_per_capita", "count"),
        )
        .sort_values("iso3")
    )
    coverage.to_csv(output_dir / "country_coverage.csv", index=False)

    cycle = pd.to_numeric(panel["level_cycle_product"], errors="coerce").dropna()
    max_abs_log_error = float(
        cycle.map(lambda x: abs(math.log(x))).max()
    ) if not cycle.empty else float("nan")

    gini_n = int(panel["gini"].notna().sum())
    complete_n = int(panel[["log_gini", "log_density", "log_gdp_per_capita"]].notna().all(axis=1).sum())

    summary = [
        "G20 cyclic quotient panel: reproducibility summary",
        f"Period requested: {start_year}-{end_year}",
        "Countries: 19 sovereign G20 country members; EU and AU aggregates excluded.",
        f"Panel rows: {len(panel)}",
        f"Rows with observed Gini: {gini_n}",
        f"Complete observations for logged regression: {complete_n}",
        f"Maximum absolute log of constructed level-cycle product: {max_abs_log_error:.3e}",
        "Interpretation: the constructed level cycle closes by algebraic cancellation. This is a consistency check, not an empirical finding or noisy-cycle test.",
        "A noisy closure test requires independent edge estimates and their joint error covariance; these are not supplied by this common-vector construction.",
    ]
    (output_dir / "data_and_cycle_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=2000, help="First calendar year (default: 2000).")
    parser.add_argument("--end", type=int, default=2023, help="Last calendar year (default: 2023).")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for downloaded panel and analysis outputs (default: outputs).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    if args.start > args.end:
        raise SystemExit("--start must be less than or equal to --end")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    panel = download_panel(args.start, args.end)
    panel = construct_measures(panel)
    panel.to_csv(args.output_dir / "g20_world_bank_panel.csv", index=False)
    make_summary(panel, args.output_dir, args.start, args.end)
    model_summary = fit_descriptive_panel_model(panel, args.output_dir)

    print(f"Saved analysis outputs to: {args.output_dir.resolve()}")
    print("\n".join(model_summary.splitlines()[:12]))
    print("\nRead data_and_cycle_summary.txt for coverage and interpretation notes.")


if __name__ == "__main__":
    main()

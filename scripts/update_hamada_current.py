#!/usr/bin/env python3
"""Fetch and append offshore current data for Hamada, Takashima, and Mishima.

Output:
  data/hamada_offshore_current_all.csv

Authentication:
  COPERNICUSMARINE_SERVICE_USERNAME / COPERNICUSMARINE_SERVICE_PASSWORD
  are read by the copernicusmarine client. In GitHub Actions these are mapped
  from repository secrets CMEMS_USERNAME / CMEMS_PASSWORD.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import copernicusmarine as cm
import numpy as np
import pandas as pd
import xarray as xr


@dataclass(frozen=True)
class Target:
    name: str
    lat: float
    lon: float


TARGETS = [
    Target("浜田沖", 34.923889, 132.013278),
    Target("高島沖", 34.845861, 131.820278),
    Target("見島沖", 34.951972, 131.077111),
]

OUTPUT_PATH = Path("data/hamada_offshore_current_all.csv")

DATASET_MY = "cmems_mod_glo_phy_my_0.083deg_P1D-m"
DATASET_AFC_CUR = "cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m"
DATASET_AFC_TMP = "cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m"
DATASET_AFC_SAL = "cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m"
FORECAST_START = date(2026, 1, 1)

COLUMNS = [
    "date",
    "point",
    "lat",
    "lon",
    "u_ms",
    "v_ms",
    "speed_ms",
    "speed_kn",
    "direction",
    "temp_c",
    "salinity",
]


def jst_yesterday() -> date:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).date() - timedelta(days=1)


def date_range(start: date, end: date) -> list[date]:
    if start > end:
        raise ValueError("start date must be before or equal to end date")
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def cmems_subset(dataset_id: str, variables: list[str], target: Target, start: date, end: date) -> xr.Dataset:
    bbox = 0.12
    return cm.open_dataset(
        dataset_id=dataset_id,
        variables=variables,
        start_datetime=f"{start.isoformat()}T00:00:00",
        end_datetime=f"{end.isoformat()}T23:59:59",
        minimum_longitude=target.lon - bbox,
        maximum_longitude=target.lon + bbox,
        minimum_latitude=target.lat - bbox,
        maximum_latitude=target.lat + bbox,
        minimum_depth=0.0,
        maximum_depth=1.0,
    )


def normalize_dataset(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    for old, new in {
        "longitude": "lon",
        "latitude": "lat",
        "uo": "u",
        "vo": "v",
        "thetao": "temp",
        "so": "salt",
    }.items():
        if old in ds:
            rename[old] = new
        if old in ds.coords:
            rename[old] = new
    return ds.rename(rename) if rename else ds


def merge_period_dataset(target: Target, dates: list[date]) -> xr.Dataset:
    start = min(dates)
    end = max(dates)
    if end < FORECAST_START:
        print(f"[open] {target.name} {start}..{end} reanalysis")
        return normalize_dataset(cmems_subset(DATASET_MY, ["uo", "vo", "thetao", "so"], target, start, end))

    if start < FORECAST_START:
        raise ValueError("Date ranges crossing 2025-12-31 must be split before fetching")

    print(f"[open] {target.name} {start}..{end} analysis/forecast")
    parts = [
        cmems_subset(DATASET_AFC_CUR, ["uo", "vo"], target, start, end),
        cmems_subset(DATASET_AFC_TMP, ["thetao"], target, start, end),
        cmems_subset(DATASET_AFC_SAL, ["so"], target, start, end),
    ]
    try:
        return normalize_dataset(xr.merge(parts, compat="override"))
    finally:
        for ds in parts:
            ds.close()


def split_by_dataset(dates: list[date]) -> list[list[date]]:
    old_dates = [d for d in dates if d < FORECAST_START]
    new_dates = [d for d in dates if d >= FORECAST_START]
    return [group for group in (old_dates, new_dates) if group]


def nearest_value(ds: xr.Dataset, var_name: str, target: Target, target_date: date) -> float:
    if var_name not in ds:
        return float("nan")

    da = ds[var_name]
    if "time" in da.dims:
        dates = pd.to_datetime(da["time"].values).date
        matches = np.where(dates == target_date)[0]
        if len(matches):
            da = da.isel(time=int(matches[0]))
        else:
            da = da.sel(time=np.datetime64(target_date.isoformat()), method="nearest")

    if "depth" in da.dims:
        da = da.isel(depth=0)

    if "lat" in da.dims and "lon" in da.dims:
        da = da.sel(lat=target.lat, lon=target.lon, method="nearest")
    elif "latitude" in da.dims and "longitude" in da.dims:
        da = da.sel(latitude=target.lat, longitude=target.lon, method="nearest")

    value = float(np.asarray(da.values).squeeze())
    return value if math.isfinite(value) else float("nan")


def speed_ms(u: float, v: float) -> float:
    if not math.isfinite(u) or not math.isfinite(v):
        return float("nan")
    return math.sqrt(u * u + v * v)


def direction_deg(u: float, v: float) -> float:
    if not math.isfinite(u) or not math.isfinite(v):
        return float("nan")
    return (math.degrees(math.atan2(u, v)) + 360) % 360


def rounded(value: float, digits: int) -> float | None:
    return round(value, digits) if math.isfinite(value) else None


def row_from_dataset(ds: xr.Dataset, target: Target, target_date: date) -> dict:
    u = nearest_value(ds, "u", target, target_date)
    v = nearest_value(ds, "v", target, target_date)
    spd_ms = speed_ms(u, v)
    return {
        "date": target_date.isoformat(),
        "point": target.name,
        "lat": target.lat,
        "lon": target.lon,
        "u_ms": rounded(u, 4),
        "v_ms": rounded(v, 4),
        "speed_ms": rounded(spd_ms, 4),
        "speed_kn": rounded(spd_ms * 1.944, 4),
        "direction": rounded(direction_deg(u, v), 1),
        "temp_c": rounded(nearest_value(ds, "temp", target, target_date), 2),
        "salinity": rounded(nearest_value(ds, "salt", target, target_date), 3),
    }


def fetch_rows(target: Target, dates: list[date]) -> list[dict]:
    rows: list[dict] = []
    for group in split_by_dataset(dates):
        ds = merge_period_dataset(target, group)
        try:
            for d in group:
                print(f"[extract] {d.isoformat()} {target.name}")
                rows.append(row_from_dataset(ds, target, d))
        finally:
            ds.close()
    return rows


def existing_keys(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "date" not in df.columns:
        return set()
    if "point" not in df.columns:
        df["point"] = TARGETS[0].name
    return set(zip(df["date"].astype(str), df["point"].astype(str)))


def save_rows(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    new_df = pd.DataFrame(rows, columns=COLUMNS)
    if output_path.exists():
        old_df = pd.read_csv(output_path, encoding="utf-8-sig")
        if "point" not in old_df.columns:
            old_df["point"] = TARGETS[0].name
        df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        df = new_df
    df.drop_duplicates(subset=["date", "point"], keep="last", inplace=True)
    df.sort_values(["point", "date"], inplace=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[ok] wrote {len(df)} rows -> {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update offshore current CSV for all dashboard points")
    parser.add_argument("--date", help="single date, e.g. 2026-05-07")
    parser.add_argument("--start", help="start date, e.g. 2026-02-07")
    parser.add_argument("--end", help="end date, e.g. 2026-05-07")
    parser.add_argument("--all", action="store_true", help="fetch from 2022-01-01 to yesterday JST")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--no-skip", action="store_true", help="overwrite existing dates and points")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)

    if args.all:
        dates = date_range(date(2022, 1, 1), jst_yesterday())
    elif args.date:
        dates = [date.fromisoformat(args.date)]
    elif args.start or args.end:
        start = date.fromisoformat(args.start) if args.start else date(2022, 1, 1)
        end = date.fromisoformat(args.end) if args.end else jst_yesterday()
        dates = date_range(start, end)
    else:
        dates = [jst_yesterday()]

    done = set() if args.no_skip else existing_keys(output_path)
    rows = []
    for target in TARGETS:
        missing = [d for d in dates if (d.isoformat(), target.name) not in done]
        if not missing:
            print(f"[ok] {target.name}: no new dates to fetch")
            continue
        rows.extend(fetch_rows(target, missing))

    if rows:
        save_rows(rows, output_path)
    else:
        print("[ok] no new dates or points to fetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

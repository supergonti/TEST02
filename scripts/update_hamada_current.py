#!/usr/bin/env python3
"""Fetch and append Hamada offshore current data from Copernicus Marine.

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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import copernicusmarine as cm


TARGET_NAME = "浜田沖"
TARGET_LAT = 34.923889
TARGET_LON = 132.013278
OUTPUT_PATH = Path("data/hamada_offshore_current_all.csv")

DATASET_MY = "cmems_mod_glo_phy_my_0.083deg_P1D-m"
DATASET_AFC_CUR = "cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m"
DATASET_AFC_TMP = "cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m"
DATASET_AFC_SAL = "cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m"

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
    return (datetime.now(jst).date() - timedelta(days=1))


def date_range(start: date, end: date) -> list[date]:
    if start > end:
        raise ValueError("start date must be before or equal to end date")
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def cmems_subset(dataset_id: str, variables: list[str], target_date: date) -> xr.Dataset:
    bbox = 0.12
    return cm.open_dataset(
        dataset_id=dataset_id,
        variables=variables,
        start_datetime=f"{target_date.isoformat()}T00:00:00",
        end_datetime=f"{target_date.isoformat()}T23:59:59",
        minimum_longitude=TARGET_LON - bbox,
        maximum_longitude=TARGET_LON + bbox,
        minimum_latitude=TARGET_LAT - bbox,
        maximum_latitude=TARGET_LAT + bbox,
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


def merge_daily_dataset(target_date: date) -> xr.Dataset:
    if target_date <= date(2025, 12, 31):
        return normalize_dataset(cmems_subset(DATASET_MY, ["uo", "vo", "thetao", "so"], target_date))

    parts = [
        cmems_subset(DATASET_AFC_CUR, ["uo", "vo"], target_date),
        cmems_subset(DATASET_AFC_TMP, ["thetao"], target_date),
        cmems_subset(DATASET_AFC_SAL, ["so"], target_date),
    ]
    try:
        return normalize_dataset(xr.merge(parts, compat="override"))
    finally:
        for ds in parts:
            ds.close()


def nearest_value(ds: xr.Dataset, var_name: str) -> float:
    if var_name not in ds:
        return float("nan")

    da = ds[var_name]
    selection = {}
    for dim in da.dims:
        if dim == "time":
            selection[dim] = 0
        elif dim == "depth":
            selection[dim] = 0

    if selection:
        da = da.isel(**selection)

    if "lat" in da.dims and "lon" in da.dims:
        da = da.sel(lat=TARGET_LAT, lon=TARGET_LON, method="nearest")
    elif "latitude" in da.dims and "longitude" in da.dims:
        da = da.sel(latitude=TARGET_LAT, longitude=TARGET_LON, method="nearest")

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


def fetch_day(target_date: date) -> dict:
    print(f"[fetch] {target_date.isoformat()} {TARGET_NAME}")
    ds = merge_daily_dataset(target_date)
    try:
        u = nearest_value(ds, "u")
        v = nearest_value(ds, "v")
        spd_ms = speed_ms(u, v)
        return {
            "date": target_date.isoformat(),
            "point": TARGET_NAME,
            "lat": TARGET_LAT,
            "lon": TARGET_LON,
            "u_ms": rounded(u, 4),
            "v_ms": rounded(v, 4),
            "speed_ms": rounded(spd_ms, 4),
            "speed_kn": rounded(spd_ms * 1.944, 4),
            "direction": rounded(direction_deg(u, v), 1),
            "temp_c": rounded(nearest_value(ds, "temp"), 2),
            "salinity": rounded(nearest_value(ds, "salt"), 3),
        }
    finally:
        ds.close()


def existing_dates(path: Path) -> set[str]:
    if not path.exists():
        return set()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "date" not in df.columns:
        return set()
    return set(df["date"].astype(str))


def save_rows(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    new_df = pd.DataFrame(rows, columns=COLUMNS)
    if output_path.exists():
        old_df = pd.read_csv(output_path, encoding="utf-8-sig")
        df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        df = new_df
    df.drop_duplicates(subset=["date", "point"], keep="last", inplace=True)
    df.sort_values(["date", "point"], inplace=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[ok] wrote {len(df)} rows -> {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Hamada offshore current CSV")
    parser.add_argument("--date", help="single date, e.g. 2026-05-07")
    parser.add_argument("--start", help="start date, e.g. 2026-05-01")
    parser.add_argument("--end", help="end date, e.g. 2026-05-07")
    parser.add_argument("--all", action="store_true", help="fetch from 2022-01-01 to yesterday JST")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--no-skip", action="store_true", help="overwrite existing dates")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)

    if args.all:
        dates = date_range(date(2022, 1, 1), jst_yesterday())
    elif args.date:
        one = date.fromisoformat(args.date)
        dates = [one]
    elif args.start or args.end:
        start = date.fromisoformat(args.start) if args.start else date(2022, 1, 1)
        end = date.fromisoformat(args.end) if args.end else jst_yesterday()
        dates = date_range(start, end)
    else:
        dates = [jst_yesterday()]

    done = set() if args.no_skip else existing_dates(output_path)
    rows = []
    for d in dates:
        if d.isoformat() in done:
            print(f"[skip] {d.isoformat()} already exists")
            continue
        rows.append(fetch_day(d))

    if rows:
        save_rows(rows, output_path)
    else:
        print("[ok] no new dates to fetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

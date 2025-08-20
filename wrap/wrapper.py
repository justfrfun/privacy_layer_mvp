from __future__ import annotations
import os
from pathlib import Path
import pandas as pd

def enforce_schema(df: pd.DataFrame, schema: dict, strict: bool=False, out_dir: str|None=None):
    """Cast dtypes, validate dates, and optionally quarantine raw bad rows.
    Returns (clean_df, info_dict).
    info_dict contains {quarantined_rows, quarantine_path}.
    """
    info = {"quarantined_rows": 0, "quarantine_path": None}

    # Casts
    dtypes = (schema or {}).get("dtypes", {})
    for col, typ in dtypes.items():
        if col not in df.columns: 
            continue
        try:
            if typ == "float":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif typ == "int":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            elif typ == "str":
                df[col] = df[col].astype("string")
        except Exception:
            # permissive: leave as-is
            pass

    # Date handling
    fmt = (schema or {}).get("date_format", "%Y-%m-%d")
    strict_dates = bool((schema or {}).get("strict_dates", False))
    if "date" in df.columns:
        strict_parsed = pd.to_datetime(df["date"], format=fmt, errors="coerce")
        bad_mask = strict_parsed.isna() & df["date"].notna()

        if strict_dates and bad_mask.any():
            if strict:
                sample = df.loc[bad_mask, "date"].astype(str).head().tolist()
                raise ValueError(f"Strict dates enabled: {bad_mask.sum()} rows do not match {fmt}. Examples: {sample}")
            else:
                if out_dir:
                    Path(out_dir).mkdir(parents=True, exist_ok=True)
                    raw_path = Path(out_dir) / "quarantine_raw.csv"
                    bad_df = df.loc[bad_mask].copy()
                    bad_df["quarantine_reason"] = "invalid_date_format"
                    header = not raw_path.exists()
                    bad_df.to_csv(raw_path, index=False, mode="a", header=header)
                    info["quarantine_path"] = str(raw_path)
                    info["quarantined_rows"] = int(bad_mask.sum())
                keep_mask = ~bad_mask
                df = df.loc[keep_mask].copy()

        # finally, normalize good dates to uniform format
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime(fmt)

    return df, info

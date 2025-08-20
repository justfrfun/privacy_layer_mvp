import os, json, argparse
from pathlib import Path
import pandas as pd

from tok.tokenizer import tok, mask_fpe_last4
from pii.detector import load_policy, detect_in_row
from wrap.wrapper import enforce_schema

def human_exit(msg: str) -> None:
    print(f"[error] {msg}")
    raise SystemExit(1)

def write_log(out_dir: str, meta: dict) -> str:
    out = Path(out_dir) / "governance_log.json"
    out.write_text(json.dumps(meta, indent=2))
    return str(out)

def process(input_path: str, out_dir: str, policy_path: str, strict: bool = False):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    input_path = Path(input_path)
    if not input_path.exists():
        human_exit(f"Input file not found: {input_path}")

    try:
        df = pd.read_csv(input_path)
    except Exception as e:
        human_exit(f"Failed to read CSV: {e}")

    # Load policy
    policy = load_policy(policy_path)

    # Required columns check
    required = policy.get("schema", {}).get("required_columns", [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        if strict:
            human_exit(f"Missing required columns: {missing}")
        else:
            print(f"[warn] Missing required columns (non-strict): {missing}")

    # Ensure PII columns are string before we mutate
    pii_cols = [c for c in policy.get("pii_fields", {}).keys() if c in df.columns]
    if pii_cols:
        df[pii_cols] = df[pii_cols].astype("string")

    # --- Schema enforcement (casts & date normalization; may quarantine rows) ---
    schema_info = {"quarantined_rows": 0, "quarantine_path": None}
    try:
        df, schema_info = enforce_schema(
            df,
            policy.get("schema", {}),
            strict=bool(strict),
            out_dir=out_dir,
        )
    except Exception as e:
        if strict:
            human_exit(f"Schema enforcement failed: {e}")
        else:
            print(f"[warn] Schema enforcement warning: {e}")

    # --- PII detection + masking/tokenization ---
    actions_applied = []
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        try:
            hits = detect_in_row(row_dict, policy)
        except Exception as e:
            if strict:
                human_exit(f"PII detection failed on row {idx}: {e}")
            else:
                print(f"[warn] PII detection failed on row {idx}: {e}")
                continue

        for field, action, value in hits:
            try:
                # make sure destination cell can hold string
                if field in df.columns and df[field].dtype != "object":
                    df[field] = df[field].astype("string")

                if action == "tokenize":
                    df.at[idx, field] = tok(str(value), field)
                elif action == "mask_fpe_last4":
                    df.at[idx, field] = mask_fpe_last4(value)
                actions_applied.append({"row": int(idx), "field": field, "action": action})
            except Exception as e:
                if strict:
                    human_exit(f"Transform failed on row {idx} / field {field}: {e}")
                else:
                    print(f"[warn] Transform failed on row {idx} / field {field}: {e}")

    # --- Write primary outputs ---
    masked_csv = os.path.join(out_dir, "dataset_masked.csv")
    try:
        df.to_csv(masked_csv, index=False)
    except Exception as e:
        human_exit(f"Failed to write CSV: {e}")

    parquet_path = None
    try:
        parquet_path = os.path.join(out_dir, "dataset_masked.parquet")
        df.to_parquet(parquet_path, index=False)
    except Exception as e:
        parquet_path = None
        print(f"[warn] Parquet write failed (install pyarrow?): {e}")

    # --- If there is a raw quarantine, also produce a masked copy ---
    qraw = schema_info.get("quarantine_path")
    if qraw and Path(qraw).exists():
        try:
            masked_qdf = pd.read_csv(qraw).copy()
            for idx, row in masked_qdf.iterrows():
                row_dict = row.to_dict()
                try:
                    qhits = detect_in_row(row_dict, policy)
                except Exception as e:
                    print(f"[warn] Quarantine masking detection failed on row {idx}: {e}")
                    continue
                for field, action, value in qhits:
                    try:
                        if field in masked_qdf.columns and masked_qdf[field].dtype != "object":
                            masked_qdf[field] = masked_qdf[field].astype("string")
                        if action == "tokenize":
                            masked_qdf.at[idx, field] = tok(str(value), field)
                        elif action == "mask_fpe_last4":
                            masked_qdf.at[idx, field] = mask_fpe_last4(value)
                    except Exception as e:
                        print(f"[warn] Quarantine transform failed on row {idx} / field {field}: {e}")
            qmasked_path = os.path.join(out_dir, "quarantine_masked.csv")
            masked_qdf.to_csv(qmasked_path, index=False)
            schema_info["quarantine_masked_path"] = str(qmasked_path)
        except Exception as e:
            print(f"[warn] Failed to produce masked quarantine copy: {e}")

    # --- Governance log ---
    meta = {
        "policy": policy.get("name"),
        "policy_version": policy.get("version"),
        "input": str(input_path),
        "output_csv": str(masked_csv),
        "output_parquet": str(parquet_path) if parquet_path else None,
        "totals": {"rows": len(df), "actions": len(actions_applied)},
        "strict_mode": bool(strict),
        "extra_columns": [c for c in df.columns if c not in required],
        "quarantined_rows": int(schema_info.get("quarantined_rows", 0)),
        "quarantine_path": schema_info.get("quarantine_path") or "",
        "quarantine_masked_path": schema_info.get("quarantine_masked_path") or "",
    }
    log_path = write_log(out_dir, meta)

    return str(masked_csv), (str(parquet_path) if parquet_path else None), str(log_path)


def main():
    p = argparse.ArgumentParser(
        description="Privacy-aware masking/tokenization + universal wrapper"
    )
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    process(args.input, args.out, args.policy, strict=args.strict)


if __name__ == "__main__":
    main()

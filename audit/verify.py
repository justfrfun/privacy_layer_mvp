import re
import json
import sys, os
from pathlib import Path
import pandas as pd

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PAN_RE   = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

def load_outputs(out_dir: Path):
    parquet = out_dir / "dataset_masked.parquet"
    csv = out_dir / "dataset_masked.csv"
    log_path = out_dir / "governance_log.json"
    if parquet.exists():
        df = pd.read_parquet(parquet)
    else:
        df = pd.read_csv(csv)
    meta = json.loads(log_path.read_text())
    return df, meta
def find_raw_pii(df: pd.DataFrame):
    """Scan all string columns for obvious PII that should have been masked."""
    leaks = []
    for col in df.columns:
        if str(df[col].dtype) not in ("object", "string"):
            continue
        sample = df[col].astype("string").fillna("").head(2000)  # limit scan
        # raw emails present?
        if sample.str.contains(EMAIL_RE).any():
            leaks.append((col, "email_pattern"))
        # long digit sequences (PAN-ish)
        if sample.str.contains(PAN_RE).any():
            leaks.append((col, "long_digit_sequence"))
    return leaks

def check_tokens(df: pd.DataFrame, expected_token_cols):
    """Ensure that expected tokenized columns contain <PII:...:...> patterns (or are NA)."""
    issues = []
    TOKEN_RE = re.compile(r"^<PII:[A-Za-z0-9_]+:[A-Za-z0-9_\-]+>$")
    for col in expected_token_cols:
        if col not in df.columns:
            issues.append((col, "missing_column"))
            continue
        s = df[col].astype("string").fillna("")
        mask_ok = s[s.ne("")].str.match(TOKEN_RE).all()
        if not mask_ok:
            bad = s[(s.ne("")) & (~s.str.match(TOKEN_RE))].head(5).tolist()
            issues.append((col, f"non_token_values: {bad}"))
    return issues

def main(out_dir="out", policy_path="configs/fintech_default.json"):
    out_dir = Path(out_dir)
    df, meta = load_outputs(out_dir)

    # Load policy to know which columns should be tokenized
    with open(policy_path) as f:
        policy = json.load(f)
    expected_token_cols = [k for k,v in policy.get("pii_fields",{}).items() if v == "tokenize"]

    pii_leaks = find_raw_pii(df)
    token_issues = check_tokens(df, expected_token_cols)

    print("\n=== Audit Results ===")
    print(f"Rows: {len(df)}")
    print(f"Policy: {meta.get('policy')} v{meta.get('policy_version')}")
    print(f"Actions logged: {meta.get('totals',{}).get('actions')}")

    if not pii_leaks:
        print("PII scan: ✅ no obvious emails or long PAN-like numbers found.")
    else:
        print("PII scan: ⚠️ potential leaks found:")
        for col, kind in pii_leaks:
            print(f"  - {col}: {kind}")

    if not token_issues:
        print("Token columns: ✅ expected token columns look correct.")
    else:
        print("Token columns: ⚠️ issues:")
        for col, msg in token_issues:
            print(f"  - {col}: {msg}")

    # simple pass/fail
    ok = (not pii_leaks) and (not token_issues)
    q_rows = meta.get("quarantined_rows")
    q_path = meta.get("quarantine_path") or meta.get("quarantined_path")
    if q_rows is not None:
        print(f"Quarantined rows: {q_rows} (path: {q_path})")
    print("\nOVERALL:", "PASS ✅" if ok else "FAIL ❌")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OUT_DIR", "out")
    policy_path = (
        sys.argv[2] if len(sys.argv) > 2 else os.environ.get("POLICY_PATH", "configs/fintech_default.json")
    )
    main(out_dir=out_dir, policy_path=policy_path)
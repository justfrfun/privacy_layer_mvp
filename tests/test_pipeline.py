# tests/test_pipeline.py
import json, re
from pathlib import Path
import pandas as pd

from cli.process import process  # uses the pipeline function you already have

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PAN_RE   = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
TOKEN_RE = re.compile(r"^<PII:[A-Za-z0-9_]+:[A-Za-z0-9_\-]+>$")

def test_end_to_end(tmp_path):
    root = Path(__file__).resolve().parents[1]
    input_path = root / "data" / "sample_transactions.csv"
    policy_path = root / "configs" / "fintech_default.json"
    out_dir = tmp_path / "out"

    csv_out, pq_out, log_out = process(str(input_path), str(out_dir), str(policy_path))

    # outputs exist
    assert Path(csv_out).exists()
    assert Path(log_out).exists()

    # prefer parquet if present
    if pq_out:
        df = pd.read_parquet(pq_out)
    else:
        df = pd.read_csv(csv_out)

    # 1) no obvious raw PII in outputs
    for col in df.columns:
        s = df[col].astype("string").fillna("")
        assert not s.str.contains(EMAIL_RE).any(), f"email leak in {col}"
        assert not s.str.contains(PAN_RE).any(),   f"PAN-like leak in {col}"

    # 2) tokenized columns look like tokens
    policy = json.loads(Path(policy_path).read_text())
    token_cols = [k for k,v in policy.get("pii_fields",{}).items() if v == "tokenize"]
    for col in token_cols:
        assert col in df.columns
        s = df[col].astype("string").fillna("")
        bad = s[(s != "") & ~s.str.match(TOKEN_RE)]
        assert bad.empty, f"{col} contains non-token values: {bad.head().tolist()}"

    # 3) date normalization & required columns
    req = policy.get("schema",{}).get("required_columns",[])
    for col in req:
        assert col in df.columns
    assert df["date"].astype("string").str.match(r"^\d{4}-\d{2}-\d{2}$").all()
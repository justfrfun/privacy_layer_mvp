# tests/test_edge_cases.py
import pandas as pd
import tempfile
import os
import pytest
from pathlib import Path

from cli.process import process as run_pipeline  # <-- direct function

def write_temp_csv(rows):
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv")
    pd.DataFrame(rows).to_csv(tmp.name, index=False)
    tmp.close()
    return tmp.name

def run_process(input_file, out_dir, strict=False):
    out_dir = str(out_dir)
    return run_pipeline(input_file, out_dir, "configs/fintech_default.json", strict=strict)

def test_malformed_csv_strict_fails(tmp_path):
    bad_csv = write_temp_csv([{"merchant": "Test"}])  # missing required cols
    out_dir = tmp_path / "out"
    with pytest.raises(SystemExit):  # human_exit -> sys.exit -> SystemExit
        run_process(bad_csv, out_dir, strict=True)

def test_partial_pii_masking(tmp_path):
    data = [
        {"transaction_id": 1, "date": "2025-01-01", "merchant": "Shop", "amount": 10,
         "customer_name": "John Doe", "customer_email": "", "card_number": "", "city": "", "state": "", "zip": "", "account_id": "acc123"},
        {"transaction_id": 2, "date": "2025-01-02", "merchant": "Shop", "amount": 20,
         "customer_name": "", "customer_email": "", "card_number": "", "city": "", "state": "", "zip": "", "account_id": ""}
    ]
    csv_file = write_temp_csv(data)
    out_dir = tmp_path / "out"
    csv_out, pq_out, log_out = run_process(csv_file, out_dir)
    df = pd.read_csv(csv_out, keep_default_na=False) # <-keep empty strings as ""
    assert "<PII:customer_name" in df.iloc[0]["customer_name"]
    assert df.iloc[1]["customer_name"] == ""

def test_large_number_not_masked(tmp_path):
    data = [
        {"transaction_id": 1, "date": "2025-01-01", "merchant": "Shop", "amount": 9999999999,
         "customer_name": "", "customer_email": "", "card_number": "", "city": "", "state": "", "zip": "", "account_id": ""}
    ]
    csv_file = write_temp_csv(data)
    out_dir = tmp_path / "out"
    csv_out, pq_out, log_out = run_process(csv_file, out_dir)
    df = pd.read_csv(csv_out)
    assert df.loc[0, "amount"] == 9999999999
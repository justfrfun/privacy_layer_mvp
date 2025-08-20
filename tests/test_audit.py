# tests/test_audit.py
from audit.verify import find_raw_pii, check_tokens
import pandas as pd

def test_find_raw_pii_flags_emails():
    df = pd.DataFrame({"text": ["hello", "user@mail.com"]})
    leaks = find_raw_pii(df)
    assert any(col == "text" and kind == "email_pattern" for col, kind in leaks)

def test_check_tokens_accepts_token_pattern():
    df = pd.DataFrame({"customer_name": ["<PII:customer_name:abc123DEF456>"]})
    issues = check_tokens(df, expected_token_cols=["customer_name"])
    assert not issues

import re, json
from typing import Dict, Any, List, Tuple

def load_policy(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return json.load(f)

def detect_in_row(row: Dict[str, Any], policy: Dict[str, Any]) -> List[Tuple[str,str,str]]:
    """
    Return list of (field, action, value) for fields that are PII per policy.
    Also scans text fields with regex_pii.
    """
    hits = []
    for field, action in policy.get("pii_fields", {}).items():
        if field in row and str(row[field]).lower() not in ("none","nan",""):
            hits.append((field, action, str(row[field])))
    regex_cfg = policy.get("regex_pii", {})
    for name, cfg in regex_cfg.items():
        pat = re.compile(cfg["pattern"])
        action = cfg["action"]
        for k, v in row.items():
            if v is None or isinstance(v, (int, float)):
                continue
            text = str(v)
            if pat.search(text):
                hits.append((k, action, text))
    return hits

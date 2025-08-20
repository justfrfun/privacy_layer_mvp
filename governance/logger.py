
import json, hashlib, time, os
from typing import Dict, Any

def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def write_log(output_dir: str, meta: Dict[str, Any]) -> str:
    os.makedirs(output_dir, exist_ok=True)
    meta = dict(meta)
    meta["timestamp"] = int(time.time())
    path = os.path.join(output_dir, "governance_log.json")
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
    return path

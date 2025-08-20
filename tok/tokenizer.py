
import os, hmac, hashlib, base64

SECRET = os.environ.get("PRIV_LAYER_SECRET","dev-secret-change-me").encode()

def _tok_bytes(value: bytes, salt: str) -> str:
    hm = hmac.new(SECRET, msg=(salt.encode()+b"::"+value), digestmod=hashlib.sha256).digest()
    return base64.urlsafe_b64encode(hm)[:16].decode()

def tok(value: str, field: str) -> str:
    if value is None or value == '':
        return value
    v = str(value).encode()
    t = _tok_bytes(v, field)
    return f"<PII:{field}:{t}>"

def mask_fpe_last4(value: str) -> str:
    if value is None:
        return value
    s = ''.join(ch for ch in str(value) if ch.isdigit())
    if len(s) < 4:
        return "****"
    return "*"*(len(s)-4) + s[-4:]

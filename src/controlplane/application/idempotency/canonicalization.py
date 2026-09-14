"""RFC 8785 canonical JSON bytes."""
from __future__ import annotations
import hashlib,json,math
from decimal import Decimal
from typing import Any
def _key(v:str)->bytes:return v.encode("utf-16-be","surrogatepass")
def _number(v:int|float)->str:
    if isinstance(v, int):
        if abs(v) > 2**53 - 1: raise ValueError("JCS_INTEGER_OUT_OF_RANGE")
        return str(v)
    if not math.isfinite(v): raise ValueError("JCS_NON_FINITE_NUMBER")
    if v == 0: return "0"
    text=repr(v); absolute=abs(v)
    if 1e-6 <= absolute < 1e21: return format(Decimal(text), "f").rstrip("0").rstrip(".")
    mantissa, exponent = text.lower().split("e") if "e" in text.lower() else (text, "0")
    return f"{mantissa.rstrip('0').rstrip('.') if '.' in mantissa else mantissa}e{int(exponent):+d}"
def _canon(v:Any)->str:
    if v is None:return "null"
    if v is True:return "true"
    if v is False:return "false"
    if isinstance(v,str):return json.dumps(v,ensure_ascii=False,separators=(",",":"))
    if isinstance(v,(int,float)) and not isinstance(v,bool):
        return _number(v)
    if isinstance(v,list):return "["+",".join(_canon(x) for x in v)+"]"
    if isinstance(v,dict):
        if not all(isinstance(k,str) for k in v):raise ValueError("JCS_OBJECT_KEY_MUST_BE_STRING")
        return "{"+",".join(_canon(k)+":"+_canon(v[k]) for k in sorted(v,key=_key))+"}"
    raise ValueError("JCS_UNSUPPORTED_VALUE")
def canonicalize_json(v:object)->bytes:return _canon(v).encode("utf-8")
def request_hash(v:object)->str:return hashlib.sha256(canonicalize_json(v)).hexdigest()

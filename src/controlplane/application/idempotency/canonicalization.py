"""RFC 8785 canonical JSON bytes."""
from __future__ import annotations
import hashlib,json,math
from typing import Any
def _key(v:str)->bytes:return v.encode("utf-16-be","surrogatepass")
def _canon(v:Any)->str:
    if v is None:return "null"
    if v is True:return "true"
    if v is False:return "false"
    if isinstance(v,str):return json.dumps(v,ensure_ascii=False,separators=(",",":"))
    if isinstance(v,(int,float)) and not isinstance(v,bool):
        if isinstance(v,float) and not math.isfinite(v):raise ValueError("JCS_NON_FINITE_NUMBER")
        return "0" if v==0 else json.dumps(v,ensure_ascii=False,separators=(",",":"))
    if isinstance(v,list):return "["+",".join(_canon(x) for x in v)+"]"
    if isinstance(v,dict):
        if not all(isinstance(k,str) for k in v):raise ValueError("JCS_OBJECT_KEY_MUST_BE_STRING")
        return "{"+",".join(_canon(k)+":"+_canon(v[k]) for k in sorted(v,key=_key))+"}"
    raise ValueError("JCS_UNSUPPORTED_VALUE")
def canonicalize_json(v:object)->bytes:return _canon(v).encode("utf-8")
def request_hash(v:object)->str:return hashlib.sha256(canonicalize_json(v)).hexdigest()

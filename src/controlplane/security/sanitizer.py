from typing import Any
from src.controlplane.security.interfaces import SecretCredential

def sanitize_for_log(val: Any) -> str:
    """Sanitizes arbitrary values or SecretCredential objects for safe logging.
    
    Prevents credential leakage by replacing raw secret values with [REDACTED].
    """
    if isinstance(val, SecretCredential):
        return f"SecretCredential(alias={val.alias!r}, raw_secret='[REDACTED]')"
    if hasattr(val, 'raw_secret') and hasattr(val, 'alias'):
        return f"SecretCredential(alias={getattr(val, 'alias')!r}, raw_secret='[REDACTED]')"
    return str(val)

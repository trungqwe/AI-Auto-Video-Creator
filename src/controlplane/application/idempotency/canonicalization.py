"""Structural P2 JCS capability stub; no canonicalization exists during RED."""


def canonicalize_json(_: object) -> bytes:
    raise NotImplementedError("P2 RFC 8785 JCS behavior is not implemented during RED.")


def request_hash(_: object) -> str:
    raise NotImplementedError("P2 request-hash behavior is not implemented during RED.")

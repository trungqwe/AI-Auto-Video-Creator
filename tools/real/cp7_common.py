"""CP7-1: thư viện bằng chứng chung cho tests/real (chỉ stdlib; không in giá trị bí mật)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

STATUSES = ('PASS', 'FAIL', 'BLOCKED', 'NOT_OBSERVED')


@dataclass(frozen=True)
class SecretMatch:
    """Vị trí khớp mẫu bí mật (line, column tính từ 1); cố ý không giữ giá trị khớp."""
    kind: str
    line: int
    column: int
    length: int


_SECRET_PATTERNS = (
    ('google_oauth_access_token', re.compile(r'ya29\.[0-9A-Za-z_-]{20,}')),
    ('google_oauth_refresh_token', re.compile(r'(?<![0-9A-Za-z])1//[0-9A-Za-z_-]{20,}')),
    ('google_oauth_client_secret', re.compile(r'GOCSPX-[0-9A-Za-z_-]{20,}')),
    ('google_api_key', re.compile(r'AIza[0-9A-Za-z_-]{20,}')),
    ('pem_private_key', re.compile(r'-{5}BEGIN [A-Z ]*PRIVATE KEY-{5}')),
    ('canary', re.compile(r'cp7-canary', re.IGNORECASE)),
)
_GATE = re.compile(r'RG-[0-9]{2}')
_ITEM = re.compile(r'[a-z][a-z0-9_]*')


def _require_text(text):
    if not isinstance(text, str):
        raise TypeError('text must be str')


def scan_secrets(text):
    """Trả danh sách SecretMatch (không chứa giá trị) theo thứ tự dòng, cột."""
    _require_text(text)
    found = []
    for kind, pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            column = match.start() - (text.rfind('\n', 0, match.start()) + 1) + 1
            found.append(SecretMatch(kind, line, column, match.end() - match.start()))
    return sorted(found, key=lambda m: (m.line, m.column, m.kind))


def redact(text):
    """Thay mỗi chuỗi khớp bằng `[REDACTED:<kind>]`."""
    _require_text(text)
    for kind, pattern in _SECRET_PATTERNS:
        text = pattern.sub(f'[REDACTED:{kind}]', text)
    return text


def report_line(gate, item, status):
    """Trả đúng một dòng `RG-<mã>.<mục>: <TRẠNG THÁI>`; lỗi không lặp lại giá trị đầu vào."""
    if not (isinstance(gate, str) and _GATE.fullmatch(gate)):
        raise ValueError('invalid gate, expected RG-NN')
    if not (isinstance(item, str) and _ITEM.fullmatch(item)):
        raise ValueError('invalid item, expected [a-z][a-z0-9_]*')
    if status not in STATUSES:
        raise ValueError('invalid status, expected one of ' + ', '.join(STATUSES))
    return f'{gate}.{item}: {status}'


class CostCeilingExceeded(RuntimeError):
    """Chi phí cộng phần dự kiến vượt trần."""


class DeadlineExceeded(TimeoutError):
    """Hết thời hạn cứng."""


def _amount(name, value):
    try:
        number = Decimal(str(value))
    except ArithmeticError:
        raise ValueError(f'{name} must be a decimal amount') from None
    if not number.is_finite() or number < 0:
        raise ValueError(f'{name} must be a finite amount >= 0')
    return number


class CostGuard:
    """Dừng khi chi phí USD vượt trần; chỉ gọi ledger.records, không bao giờ ghi sổ."""

    def __init__(self, ceiling_usd, read_spent):
        self._ceiling = _amount('ceiling_usd', ceiling_usd)
        self._read_spent = read_spent

    @classmethod
    def from_ledger(cls, ledger, workspace_id, window_start, window_end, ceiling_usd):
        def read_spent():
            total = Decimal(0)
            for record in ledger.records(workspace_id, window_start, window_end):
                if record.currency != 'USD':
                    raise ValueError('ledger record currency is not USD')
                cost = record.actual_cost if record.actual_cost is not None else record.estimated_cost
                total += _amount('record cost', cost)
            return total
        return cls(ceiling_usd, read_spent)

    @property
    def ceiling(self):
        return self._ceiling

    def spent(self):
        return _amount('spent', self._read_spent())

    def check(self, additional_usd=0):
        additional = _amount('additional_usd', additional_usd)
        spent = self.spent()
        if spent + additional > self._ceiling:
            raise CostCeilingExceeded(f'cost ceiling exceeded: spent={spent} additional={additional} ceiling={self._ceiling} USD')
        return self._ceiling - spent - additional


class Deadline:
    def __init__(self, seconds, clock=time.monotonic):
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0:
            raise ValueError('seconds must be a number > 0')
        self._clock = clock
        self._end = clock() + seconds

    def remaining(self):
        return max(0.0, self._end - self._clock())

    def expired(self):
        return self._clock() >= self._end

    def check(self):
        if self.expired():
            raise DeadlineExceeded('deadline exceeded')

    def timeout(self, cap=None):
        self.check()
        remaining = self.remaining()
        return remaining if cap is None else min(remaining, cap)


def explicit_real_request(args, invocation_dir, real_dir):
    """True khi một đối số dòng lệnh trỏ vào bên trong real_dir (thư mục cha như `tests` không tính)."""
    real = Path(real_dir).resolve()
    base = Path(invocation_dir)
    for arg in args:
        arg = str(arg)
        if not arg or arg.startswith('-'):
            continue
        target = Path(arg.split('::', 1)[0])
        if not target.is_absolute():
            target = base / target
        try:
            target.resolve().relative_to(real)
        except (ValueError, OSError):
            continue
        return True
    return False

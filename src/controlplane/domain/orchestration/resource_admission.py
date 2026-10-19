"""G-12: resource admission (D8-G-06, D8-G-07; CT-WF-007).

Pure domain: không I/O, không đồng hồ, không đọc cấu hình. Ngưỡng là tham số bắt buộc lấy từ cấu hình J, không có giá trị mặc định (D8-G-07). CPU/GPU/RAM/mạng bão hòa là Deferred (backpressure: job không vào WAITING và không bao giờ thất bại cuối cùng); thiếu đĩa là Wait(insufficient_disk).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from controlplane.domain.orchestration.job_waiting import Wait, WaitReason


class DeferralCode(StrEnum):
    CPU_SATURATED = 'CPU_SATURATED'
    GPU_BUSY = 'GPU_BUSY'
    RAM_LOW = 'RAM_LOW'
    NETWORK_DOWN = 'NETWORK_DOWN'


def _int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f'{name} must be int')
    if value < 0:
        raise ValueError(f'{name} must be >= 0')


def _percent(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f'{name} must be a number')
    if not 0 <= value <= 100:
        raise ValueError(f'{name} must be within 0..100')


def _flag(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise TypeError(f'{name} must be bool')


@dataclass(frozen=True)
class AdmissionLimits:
    cpu_max_percent: float
    ram_reserve_mb: int
    disk_reserve_mb: int

    def __post_init__(self) -> None:
        _percent('cpu_max_percent', self.cpu_max_percent)
        _int('ram_reserve_mb', self.ram_reserve_mb)
        _int('disk_reserve_mb', self.disk_reserve_mb)


@dataclass(frozen=True)
class ResourceSnapshot:
    cpu: float
    gpu_slots_free: int
    ram_free_mb: int
    disk_free_mb: int
    network_ok: bool

    def __post_init__(self) -> None:
        _percent('cpu', self.cpu)
        _int('gpu_slots_free', self.gpu_slots_free)
        _int('ram_free_mb', self.ram_free_mb)
        _int('disk_free_mb', self.disk_free_mb)
        _flag('network_ok', self.network_ok)


@dataclass(frozen=True)
class ResourceNeed:
    gpu_slots: int
    ram_mb: int
    disk_mb: int
    needs_network: bool

    def __post_init__(self) -> None:
        _int('gpu_slots', self.gpu_slots)
        _int('ram_mb', self.ram_mb)
        _int('disk_mb', self.disk_mb)
        _flag('needs_network', self.needs_network)


@dataclass(frozen=True)
class Admitted:
    pass


@dataclass(frozen=True)
class Deferred:
    code: DeferralCode

    def __post_init__(self) -> None:
        if not isinstance(self.code, DeferralCode):
            raise TypeError('code must be DeferralCode')


def decide_admission(limits: AdmissionLimits, snapshot: ResourceSnapshot, need: ResourceNeed) -> Admitted | Deferred | Wait:
    if not isinstance(limits, AdmissionLimits) or not isinstance(snapshot, ResourceSnapshot) or not isinstance(need, ResourceNeed):
        raise TypeError('limits, snapshot and need must be AdmissionLimits, ResourceSnapshot and ResourceNeed')
    if need.needs_network and not snapshot.network_ok:
        return Deferred(DeferralCode.NETWORK_DOWN)
    if snapshot.cpu >= limits.cpu_max_percent:
        return Deferred(DeferralCode.CPU_SATURATED)
    if need.gpu_slots > snapshot.gpu_slots_free:
        return Deferred(DeferralCode.GPU_BUSY)
    if snapshot.ram_free_mb - need.ram_mb < limits.ram_reserve_mb:
        return Deferred(DeferralCode.RAM_LOW)
    if snapshot.disk_free_mb - need.disk_mb < limits.disk_reserve_mb:
        return Wait(WaitReason.INSUFFICIENT_DISK)
    return Admitted()


__all__ = ['AdmissionLimits', 'Admitted', 'DeferralCode', 'Deferred', 'ResourceNeed', 'ResourceSnapshot', 'Wait', 'WaitReason', 'decide_admission']

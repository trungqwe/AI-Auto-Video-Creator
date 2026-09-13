"""Domain interfaces package."""
from controlplane.domain.interfaces.uow import IUnitOfWork
from controlplane.domain.interfaces.repository import IRepository
from controlplane.domain.interfaces.statemachine import IStateMachine
from controlplane.domain.interfaces.outbox import IOutboxWriter
from controlplane.domain.interfaces.vault import ISecretVault

__all__ = [
    "IUnitOfWork",
    "IRepository",
    "IStateMachine",
    "IOutboxWriter",
    "ISecretVault",
]

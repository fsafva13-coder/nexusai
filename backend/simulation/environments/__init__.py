from .base import Environment, GatherResult
from .disaster import DisasterEnvironment
from .ecosystem import EcosystemEnvironment
from .market import MarketEnvironment

ENVIRONMENTS = {
    "disaster": DisasterEnvironment,
    "market": MarketEnvironment,
    "ecosystem": EcosystemEnvironment,
}

__all__ = [
    "ENVIRONMENTS", "Environment", "GatherResult",
    "DisasterEnvironment", "MarketEnvironment", "EcosystemEnvironment",
]

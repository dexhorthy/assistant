from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Generic, Self, TypeVar


@dataclass
class BaseEvent:
    """Base class for all events from any source"""

    id: str
    source_type: str

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw_source: str | None = None


S = TypeVar('S')  # Source type
E = TypeVar('E', bound=BaseEvent)  # Event type


class Observer(Generic[S, E], ABC):
    """Core protocol for observing sources of information

    This is the base protocol for all observers. Each observer is responsible for:
    1. Connecting to its source
    2. Converting raw source data into well-structured events
    3. Maintaining its own state/connections
    """

    @abstractmethod
    def connect(self) -> None:
        """Initialize connection to the source"""
        pass

    @abstractmethod
    async def observe(self) -> AsyncIterator[E]:
        """Stream events from the source"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Clean up connection to the source"""
        pass

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.disconnect()

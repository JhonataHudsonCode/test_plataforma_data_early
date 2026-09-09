from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar


TClient = TypeVar("TClient")


class BaseConnection(ABC, Generic[TClient]):
    """Contrato mínimo para qualquer tecnologia externa."""

    @abstractmethod
    def connect(self) -> TClient:
        """Cria ou retorna a conexão/cliente ativo."""

    @abstractmethod
    def close(self) -> None:
        """Libera recursos da conexão/cliente."""

    @property
    @abstractmethod
    def client(self) -> TClient:
        """Retorna um cliente pronto para uso."""
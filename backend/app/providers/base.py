from abc import ABC, abstractmethod
from ..models.product import ProductListing


class LocationContextError(RuntimeError):
    pass


class ProviderSearchError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class GroceryProvider(ABC):
    name: str

    @abstractmethod
    async def establish_location(self, location: str) -> None:
        """Set and verify the provider's delivery location before searching."""

    @abstractmethod
    async def search(self, query: str, location: str) -> list[ProductListing]:
        """Search only after a verified location context exists."""

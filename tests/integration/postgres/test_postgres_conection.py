import pytest

from src.repositories.postgres_catalog_repository import PostgresCatalogRepository


@pytest.mark.integration
@pytest.mark.postgres
def test_should_connect_to_postgres(
    postgres_repository: PostgresCatalogRepository,
) -> None:
    is_connected = postgres_repository.check_connection()

    assert is_connected is True
import pytest

from src.repositories.opensearch_health_repository import OpenSearchHealthRepository


@pytest.mark.integration
@pytest.mark.opensearch
def test_should_connect_to_opensearch(
    opensearch_repository: OpenSearchHealthRepository,
) -> None:
    assert opensearch_repository.check_connection() is True
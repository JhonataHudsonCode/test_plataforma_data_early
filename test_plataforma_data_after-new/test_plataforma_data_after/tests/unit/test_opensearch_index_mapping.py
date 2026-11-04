from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.repositories.opensearch_vulnerability_repository import OpenSearchVulnerabilityRepository


def test_mapping_uses_actual_index_returned_for_alias():
    indices = MagicMock()
    indices.get_mapping.return_value = {"cliente_asset_001": {"mappings": {"properties": {"date": {"type": "date"}}}}}
    repository = OpenSearchVulnerabilityRepository(SimpleNamespace(client=SimpleNamespace(indices=indices)))

    assert repository.get_index_mapping("cliente_asset") == {"properties": {"date": {"type": "date"}}}
    indices.get_mapping.assert_called_once_with(index="cliente_asset")


def test_mapping_does_not_choose_arbitrarily_from_multiple_indices():
    indices = MagicMock()
    indices.get_mapping.return_value = {"asset_001": {"mappings": {}}, "asset_002": {"mappings": {}}}
    repository = OpenSearchVulnerabilityRepository(SimpleNamespace(client=SimpleNamespace(indices=indices)))

    with pytest.raises(ValueError, match="vários índices"):
        repository.get_index_mapping("asset")

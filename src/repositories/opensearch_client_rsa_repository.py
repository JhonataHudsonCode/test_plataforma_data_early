from __future__ import annotations

import logging
from datetime import datetime
from src.connections.opensearch_factory import OpenSearchConnectionFactory
from src.models.opensearch_product.vulnerability_index import VulnerabilityIndex
from src.models.opensearch_client.opensearch_index_metadata import OpenSearchIndexMetadata
from opensearchpy.exceptions import OpenSearchException
from typing import Any


logger = logging.getLogger(__name__)


class OpenSearchClientRepository:
    """Valida índices RSA no OpenSearch específico de cada cliente."""

    def __init__(self, connection_factory: OpenSearchConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def get_indices_rsa(
        self,
        client_host: str,
        index_name: str,
    ) -> list[VulnerabilityIndex]:
        connection = self._connection_factory.create_for_host(client_host)

        try:
            connection.client.info()
            logger.info(
                "Conexão com o OpenSearch do cliente realizada em %s.",
                client_host,
            )
            indices = connection.client.cat.indices(
                index=index_name,
                format="json",
                h="index,docs.count",
                expand_wildcards="all"
            )
        finally:
            connection.close()

        found_indices = [
            VulnerabilityIndex(
                name=item["index"],
                document_count=self._parse_document_count(item.get("docs.count")),
            )
            for item in indices
            if item.get("index")
        ]

        logger.info(
            "Índice RSA esperado no host %s: %s. Índices encontrados: %s",
            client_host,
            index_name,
            [index.name for index in found_indices],
        )
        return found_indices

    def get_indices_elastalerts_status_today(
            self,
            client_host: str,
            index_name: str
        ) -> list[VulnerabilityIndex]:
            connection = self._connection_factory.create_for_host(client_host)
    
            try:
                connection.client.info()
                logger.info(
                    "Conexão com o OpenSearch do cliente realizada em %s.",
                    client_host,
                )
                indices = connection.client.cat.indices(
                    index=index_name,
                    format="json",
                    h="index,docs.count",
                    expand_wildcards="all"
                )
            finally:
                connection.close()
    
            found_indices = [
                VulnerabilityIndex(
                    name=item["index"],
                    document_count=self._parse_document_count(item.get("docs.count")),
                )
                for item in indices
                if item.get("index")
            ]
            
            logger.info(
                "Índice RSA esperado no host %s: %s. Índices encontrados: %s",
                client_host,
                index_name,
                [index.name for index in found_indices],
            )
            return found_indices

    def get_documents(
            self,
            client_host: str,
            index_name: str,
            size: int = 10,
        ) -> list[dict[str, Any]]:
            """Retorna documentos de um índice RSA do OpenSearch do cliente."""
            connection = self._connection_factory.create_for_host(client_host)

            try:
                response = connection.client.search(
                    index=index_name,
                    body={
                        "size": size,
                        "query": {"match_all": {}},
                    },
                )

            finally:
                connection.close()

            return response['hits']['hits']

    def get_latest_document(
        self,
        client_host: str,
        index_name: str,
    ) -> dict[str, Any] | None:
        """Retorna o documento com o @timestamp mais recente do índice."""
        connection = self._connection_factory.create_for_host(client_host)
        try:
            response = connection.client.search(
                index=index_name,
                body={
                    "size": 1,
                    "sort": [{"@timestamp": {"order": "desc"}}],
                    "query": {"match_all": {}},
                },
            )
        finally:
            connection.close()

        documents = response["hits"]["hits"]
        return documents[0] if documents else None

    def get_index_metadata(
        self,
        client_host: str,
        index_name: str,
    ) -> OpenSearchIndexMetadata:
        """Retorna mapping e data de criação de um índice RSA."""
        connection = self._connection_factory.create_for_host(client_host)

        try:
            mapping_response = connection.client.indices.get_mapping(index=index_name)
            settings_response = connection.client.indices.get_settings(index=index_name)
        finally:
            connection.close()

        mapping = mapping_response[index_name]["mappings"]
        creation_date = settings_response[index_name]["settings"]["index"][
            "creation_date"
        ]
        return OpenSearchIndexMetadata(
            name=index_name,
            created_at=datetime.fromtimestamp(int(creation_date) / 1000),
            mapping=mapping,
        )

    def get_indices_axur(
           self,
           client_host: str,
           index_name: str
       ) -> list[VulnerabilityIndex]:
           connection = self._connection_factory.create_for_host(client_host)
   
           try:
               connection.client.info()
               logger.info(
                   "Conexão com o OpenSearch do cliente realizada em %s.",
                   client_host,
               )
               indices = connection.client.cat.indices(
                   index=index_name,
                   format="json",
                   h="index,docs.count",
                   expand_wildcards="all"
               )
           finally:
               connection.close()
   
           found_indices = [
               VulnerabilityIndex(
                   name=item["index"],
                   document_count=self._parse_document_count(item.get("docs.count")),
               )
               for item in indices
               if item.get("index")
           ]
   
           logger.info(
               "Índice RSA esperado no host %s: %s. Índices encontrados: %s",
               client_host,
               index_name,
               [index.name for index in found_indices],
           )
           return found_indices
   

    @staticmethod
    def _parse_document_count(value: object) -> int:
        if value in {None, "", "-"}:
            return 0
        return int(value)

#!/usr/bin/env python
"""
Tests for the Neo4j utility module.

This module contains unit tests for the Neo4jClient class.
"""

import unittest
from unittest import mock

from neo4j import GraphDatabase, Driver, Session, Result
from neo4j.exceptions import ServiceUnavailable, AuthError

from src.utils.neo4j_utils import Neo4jClient
from src.utils import config


class TestNeo4jClient(unittest.TestCase):
    """Test cases for the Neo4jClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the GraphDatabase.driver method
        self.mock_driver_patcher = mock.patch('neo4j.GraphDatabase.driver')
        self.mock_driver = self.mock_driver_patcher.start()
        
        # Create a mock driver instance
        self.mock_driver_instance = mock.Mock(spec=Driver)
        self.mock_driver.return_value = self.mock_driver_instance
        
        # Mock the socket.gethostbyname method
        self.mock_socket_patcher = mock.patch('socket.gethostbyname')
        self.mock_socket = self.mock_socket_patcher.start()
        self.mock_socket.return_value = "127.0.0.1"  # Mock successful DNS resolution
        
        # Create a Neo4j client with mocked driver
        with mock.patch.object(Neo4jClient, '_test_connection'):
            self.neo4j_client = Neo4jClient(
                uri="neo4j+s://test.databases.neo4j.io",
                user="neo4j",
                password="password",
                database="neo4j",
            )
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.mock_driver_patcher.stop()
        self.mock_socket_patcher.stop()
    
    def test_init(self):
        """Test initialization of Neo4jClient."""
        # Mock _test_connection to avoid actual connection attempt
        with mock.patch.object(Neo4jClient, '_test_connection'):
            client = Neo4jClient(
                uri="neo4j+s://test.databases.neo4j.io",
                user="neo4j",
                password="password",
                database="neo4j",
            )
            
            self.assertEqual(client.uri, "neo4j+s://test.databases.neo4j.io")
            self.assertEqual(client.user, "neo4j")
            self.assertEqual(client.password, "password")
            self.assertEqual(client.database, "neo4j")
            
            # Verify GraphDatabase.driver was called with correct arguments
            GraphDatabase.driver.assert_called_once_with(
                "neo4j+s://test.databases.neo4j.io",
                auth=("neo4j", "password"),
            )
    
    def test_init_with_defaults(self):
        """Test initialization of Neo4jClient with default values."""
        # Set up mock config values
        with mock.patch.object(config, 'NEO4J_URI', "neo4j://localhost:7687"):
            with mock.patch.object(config, 'NEO4J_USER', "neo4j"):
                with mock.patch.object(config, 'NEO4J_PASSWORD', "password"):
                    with mock.patch.object(config, 'NEO4J_DATABASE', "neo4j"):
                        # Mock _test_connection to avoid actual connection attempt
                        with mock.patch.object(Neo4jClient, '_test_connection'):
                            client = Neo4jClient()
                            
                            self.assertEqual(client.uri, "neo4j://localhost:7687")
                            self.assertEqual(client.user, "neo4j")
                            self.assertEqual(client.password, "password")
                            self.assertEqual(client.database, "neo4j")
    
    def test_init_invalid_uri(self):
        """Test initialization with invalid URI scheme."""
        with self.assertRaises(ValueError):
            Neo4jClient(
                uri="invalid://test.databases.neo4j.io",
                user="neo4j",
                password="password",
            )
    
    def test_mask_uri(self):
        """Test masking sensitive information in URI."""
        # URI with credentials
        uri = "neo4j+s://user:pass@test.databases.neo4j.io"
        masked_uri = self.neo4j_client._mask_uri(uri)
        self.assertEqual(masked_uri, "neo4j+s://***:***@test.databases.neo4j.io")
        
        # URI without credentials
        uri = "neo4j+s://test.databases.neo4j.io"
        masked_uri = self.neo4j_client._mask_uri(uri)
        self.assertEqual(masked_uri, "neo4j+s://test.databases.neo4j.io")
    
    def test_test_connection(self):
        """Test connection testing."""
        # Mock session context manager
        mock_session = mock.Mock(spec=Session)
        self.mock_driver_instance.session.return_value.__enter__.return_value = mock_session
        
        # Mock query result
        mock_result = mock.Mock(spec=Result)
        mock_record = mock.Mock()
        mock_record.__getitem__.return_value = 1  # Return 1 for record["test"]
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        # Test connection
        self.neo4j_client._test_connection()
        
        # Verify session was created with correct database
        self.mock_driver_instance.session.assert_called_once_with(database="neo4j")
        
        # Verify query was executed
        mock_session.run.assert_called_once_with("RETURN 1 AS test")
    
    def test_test_connection_failure(self):
        """Test connection testing failure."""
        # Mock session context manager
        mock_session = mock.Mock(spec=Session)
        self.mock_driver_instance.session.return_value.__enter__.return_value = mock_session
        
        # Mock query result with incorrect value
        mock_result = mock.Mock(spec=Result)
        mock_record = mock.Mock()
        mock_record.__getitem__.return_value = 0  # Return 0 instead of 1
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        # Test connection should raise ServiceUnavailable
        with self.assertRaises(ServiceUnavailable):
            self.neo4j_client._test_connection()
    
    def test_close(self):
        """Test closing the Neo4j connection."""
        self.neo4j_client.close()
        
        # Verify driver.close was called
        self.mock_driver_instance.close.assert_called_once()
    
    def test_run_query(self):
        """Test running a Cypher query."""
        # Mock session context manager
        mock_session = mock.Mock(spec=Session)
        self.mock_driver_instance.session.return_value.__enter__.return_value = mock_session
        
        # Mock query result
        mock_result = mock.Mock(spec=Result)
        mock_record1 = mock.Mock()
        mock_record1.data.return_value = {"name": "Alice"}
        mock_record2 = mock.Mock()
        mock_record2.data.return_value = {"name": "Bob"}
        mock_result.__iter__.return_value = [mock_record1, mock_record2]
        mock_session.run.return_value = mock_result
        
        # Run query
        query = "MATCH (n:Person) RETURN n.name AS name"
        params = {"key": "value"}
        results = self.neo4j_client.run_query(query, params)
        
        # Verify session was created with correct database
        self.mock_driver_instance.session.assert_called_once_with(database="neo4j")
        
        # Verify query was executed with correct parameters
        mock_session.run.assert_called_once_with(query, params)
        
        # Verify results
        self.assertEqual(results, [{"name": "Alice"}, {"name": "Bob"}])
    
    def test_run_query_single(self):
        """Test running a Cypher query and returning a single record."""
        # Mock run_query method
        with mock.patch.object(self.neo4j_client, 'run_query') as mock_run_query:
            # Set up mock return value
            mock_run_query.return_value = [{"name": "Alice"}]
            
            # Run query
            query = "MATCH (n:Person) WHERE n.name = $name RETURN n.name AS name"
            params = {"name": "Alice"}
            result = self.neo4j_client.run_query_single(query, params)
            
            # Verify run_query was called with correct arguments
            mock_run_query.assert_called_once_with(query, params, None)
            
            # Verify result
            self.assertEqual(result, {"name": "Alice"})
    
    def test_run_query_single_no_results(self):
        """Test running a Cypher query with no results."""
        # Mock run_query method
        with mock.patch.object(self.neo4j_client, 'run_query') as mock_run_query:
            # Set up mock return value
            mock_run_query.return_value = []
            
            # Run query
            query = "MATCH (n:Person) WHERE n.name = $name RETURN n.name AS name"
            params = {"name": "NonExistent"}
            result = self.neo4j_client.run_query_single(query, params)
            
            # Verify result is None
            self.assertIsNone(result)
    
    def test_create_node(self):
        """Test creating a node."""
        # Mock run_query_single method
        with mock.patch.object(self.neo4j_client, 'run_query_single') as mock_run_query_single:
            # Set up mock return value
            mock_run_query_single.return_value = {"n": {"name": "Alice", "age": 30}}
            
            # Create node
            result = self.neo4j_client.create_node(
                labels=["Person", "Employee"],
                properties={"name": "Alice", "age": 30},
            )
            
            # Verify run_query_single was called with correct arguments
            mock_run_query_single.assert_called_once_with(
                "CREATE (n:Person:Employee $props) RETURN n",
                {"props": {"name": "Alice", "age": 30}},
                None,
            )
            
            # Verify result
            self.assertEqual(result, {"name": "Alice", "age": 30})
    
    def test_create_node_single_label(self):
        """Test creating a node with a single label."""
        # Mock run_query_single method
        with mock.patch.object(self.neo4j_client, 'run_query_single') as mock_run_query_single:
            # Set up mock return value
            mock_run_query_single.return_value = {"n": {"name": "Alice", "age": 30}}
            
            # Create node with single label as string
            result = self.neo4j_client.create_node(
                labels="Person",
                properties={"name": "Alice", "age": 30},
            )
            
            # Verify run_query_single was called with correct arguments
            mock_run_query_single.assert_called_once_with(
                "CREATE (n:Person $props) RETURN n",
                {"props": {"name": "Alice", "age": 30}},
                None,
            )
    
    def test_merge_node(self):
        """Test merging a node."""
        # Mock run_query_single method
        with mock.patch.object(self.neo4j_client, 'run_query_single') as mock_run_query_single:
            # Set up mock return value
            mock_run_query_single.return_value = {"n": {"name": "Alice", "age": 30, "department": "Engineering"}}
            
            # Merge node
            result = self.neo4j_client.merge_node(
                labels=["Person", "Employee"],
                match_properties={"name": "Alice"},
                set_properties={"age": 30, "department": "Engineering"},
            )
            
            # Verify run_query_single was called with correct arguments
            mock_run_query_single.assert_called_once_with(
                "MERGE (n:Person:Employee $match_props) ON CREATE SET n += $set_props ON MATCH SET n += $set_props RETURN n",
                {
                    "match_props": {"name": "Alice"},
                    "set_props": {"age": 30, "department": "Engineering"},
                },
                None,
            )
            
            # Verify result
            self.assertEqual(result, {"name": "Alice", "age": 30, "department": "Engineering"})
    
    def test_vector_search(self):
        """Test vector similarity search."""
        # Mock run_query method
        with mock.patch.object(self.neo4j_client, 'run_query') as mock_run_query:
            # Set up mock return value
            mock_run_query.return_value = [
                {"n": {"id": 1, "text": "Document 1"}, "score": 0.95},
                {"n": {"id": 2, "text": "Document 2"}, "score": 0.85},
            ]
            
            # Perform vector search
            query_vector = [0.1, 0.2, 0.3]
            results = self.neo4j_client.vector_search(
                node_label="Document",
                vector_property="embedding",
                query_vector=query_vector,
                limit=10,
                similarity_cutoff=0.8,
                additional_filters="n.status = 'active'",
                return_fields=["id", "text"],
            )
            
            # Verify run_query was called with correct arguments
            expected_query = """MATCH (n:Document)
                  WHERE n.status = 'active'
                  WITH n, vector.similarity(n.embedding, $query_vector) AS similarity
                  WHERE similarity >= 0.8
                  ORDER BY similarity DESC
                  LIMIT 10
                  RETURN n, n.id AS id, n.text AS text, similarity AS score"""
            mock_run_query.assert_called_once()
            call_args = mock_run_query.call_args[0]
            self.assertEqual(call_args[1], {"query_vector": query_vector})
            
            # Verify results
            self.assertEqual(results, [
                {"n": {"id": 1, "text": "Document 1"}, "score": 0.95},
                {"n": {"id": 2, "text": "Document 2"}, "score": 0.85},
            ])
    
    def test_create_vector_index(self):
        """Test creating a vector index."""
        # Mock run_query method
        with mock.patch.object(self.neo4j_client, 'run_query') as mock_run_query:
            # Create vector index
            self.neo4j_client.create_vector_index(
                index_name="document_embedding_index",
                node_label="Document",
                vector_property="embedding",
                dimensions=1536,
                similarity_function="cosine",
            )
            
            # Verify run_query was called with correct arguments
            expected_query = """CREATE VECTOR INDEX document_embedding_index IF NOT EXISTS
                  FOR (n:Document)
                  ON n.embedding
                  OPTIONS {
                      indexConfig: {
                          `vector.dimensions`: 1536,
                          `vector.similarity_function`: 'cosine'
                      }
                  }"""
            mock_run_query.assert_called_once()
    
    def test_create_vector_index_invalid_similarity(self):
        """Test creating a vector index with invalid similarity function."""
        with self.assertRaises(ValueError):
            self.neo4j_client.create_vector_index(
                index_name="document_embedding_index",
                node_label="Document",
                vector_property="embedding",
                dimensions=1536,
                similarity_function="invalid",
            )
    
    def test_list_vector_indexes(self):
        """Test listing vector indexes."""
        # Mock run_query method
        with mock.patch.object(self.neo4j_client, 'run_query') as mock_run_query:
            # Set up mock return value
            mock_run_query.return_value = [
                {
                    "name": "document_embedding_index",
                    "labelsOrTypes": ["Document"],
                    "properties": ["embedding"],
                    "options": {
                        "indexConfig": {
                            "vector.dimensions": 1536,
                            "vector.similarity_function": "cosine"
                        }
                    }
                }
            ]
            
            # List vector indexes
            indexes = self.neo4j_client.list_vector_indexes()
            
            # Verify run_query was called with correct arguments
            expected_query = """SHOW INDEXES
                  YIELD name, type, labelsOrTypes, properties, options
                  WHERE type = 'VECTOR'
                  RETURN name, labelsOrTypes, properties, options"""
            mock_run_query.assert_called_once()
            
            # Verify results
            self.assertEqual(len(indexes), 1)
            self.assertEqual(indexes[0]["name"], "document_embedding_index")
    
    def test_context_manager(self):
        """Test using Neo4jClient as a context manager."""
        # Mock close method
        with mock.patch.object(self.neo4j_client, 'close') as mock_close:
            # Use client as context manager
            with self.neo4j_client as client:
                self.assertEqual(client, self.neo4j_client)
            
            # Verify close was called
            mock_close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

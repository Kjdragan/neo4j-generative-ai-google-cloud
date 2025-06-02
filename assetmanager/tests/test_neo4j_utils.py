"""
Tests for the Neo4j utilities module.
"""
import unittest
from unittest import mock

import pytest
from neo4j import Driver, Session, Transaction

from src.utils.neo4j_utils import Neo4jConnection


class TestNeo4jUtils(unittest.TestCase):
    """Test cases for the Neo4j utilities module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.uri = "neo4j+s://test.databases.neo4j.io"
        self.user = "neo4j"
        self.password = "password"
        self.database = "neo4j"
        
        # Create mock driver
        self.mock_driver_patcher = mock.patch("src.utils.neo4j_utils.GraphDatabase.driver")
        self.mock_driver_func = self.mock_driver_patcher.start()
        self.mock_driver = mock.MagicMock(spec=Driver)
        self.mock_driver_func.return_value = self.mock_driver
        
        # Create mock session
        self.mock_session = mock.MagicMock(spec=Session)
        self.mock_driver.session.return_value = self.mock_session
        
        # Create mock transaction
        self.mock_tx = mock.MagicMock(spec=Transaction)
        self.mock_session.begin_transaction.return_value = self.mock_tx
        self.mock_session.__enter__.return_value = self.mock_session
        self.mock_session.__exit__.return_value = None
        
        # Create connection
        self.connection = Neo4jConnection(
            uri=self.uri,
            user=self.user,
            password=self.password,
            database=self.database
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.mock_driver_patcher.stop()
    
    def test_connect(self):
        """Test connecting to Neo4j."""
        self.connection.connect()
        
        self.mock_driver_func.assert_called_once_with(
            self.uri,
            auth=(self.user, self.password)
        )
    
    def test_close(self):
        """Test closing the Neo4j connection."""
        self.connection.driver = self.mock_driver
        
        self.connection.close()
        
        self.mock_driver.close.assert_called_once()
    
    def test_context_manager(self):
        """Test using the connection as a context manager."""
        with Neo4jConnection(
            uri=self.uri,
            user=self.user,
            password=self.password,
            database=self.database
        ) as conn:
            pass
        
        self.mock_driver_func.assert_called_once()
        self.mock_driver.close.assert_called_once()
    
    def test_run_query(self):
        """Test running a Cypher query."""
        # Setup mock response
        mock_result = [{"name": "test", "value": 1}]
        self.mock_session.run.return_value = mock_result
        
        # Connect
        self.connection.connect()
        
        # Run query
        result = self.connection.run_query(
            "MATCH (n) RETURN n.name as name, n.value as value",
            params={"param": "value"}
        )
        
        # Verify
        self.mock_session.run.assert_called_once_with(
            "MATCH (n) RETURN n.name as name, n.value as value",
            {"param": "value"}
        )
        self.assertEqual(result, mock_result)
    
    def test_create_node(self):
        """Test creating a node."""
        # Setup mock response
        mock_record = mock.MagicMock()
        mock_record["id"] = 1
        self.mock_session.run.return_value = [mock_record]
        
        # Connect
        self.connection.connect()
        
        # Create node
        node_id = self.connection.create_node(
            label="Person",
            properties={"name": "John", "age": 30}
        )
        
        # Verify
        self.mock_session.run.assert_called_once()
        self.assertEqual(node_id, 1)
    
    def test_create_relationship(self):
        """Test creating a relationship."""
        # Setup mock response
        mock_record = mock.MagicMock()
        mock_record["id"] = 1
        self.mock_session.run.return_value = [mock_record]
        
        # Connect
        self.connection.connect()
        
        # Create relationship
        rel_id = self.connection.create_relationship(
            start_node_id=1,
            end_node_id=2,
            relationship_type="KNOWS",
            properties={"since": 2020}
        )
        
        # Verify
        self.mock_session.run.assert_called_once()
        self.assertEqual(rel_id, 1)
    
    def test_merge_node(self):
        """Test merging a node."""
        # Setup mock response
        mock_record = mock.MagicMock()
        mock_record["id"] = 1
        self.mock_session.run.return_value = [mock_record]
        
        # Connect
        self.connection.connect()
        
        # Merge node
        node_id = self.connection.merge_node(
            label="Person",
            unique_properties={"name": "John"},
            other_properties={"age": 30}
        )
        
        # Verify
        self.mock_session.run.assert_called_once()
        self.assertEqual(node_id, 1)
    
    def test_import_json(self):
        """Test importing JSON data."""
        # Setup mock response
        self.mock_session.run.return_value = []
        
        # Connect
        self.connection.connect()
        
        # Import JSON
        self.connection.import_json(
            data={"nodes": [{"id": 1, "labels": ["Person"], "properties": {"name": "John"}}]},
            merge_keys={"Person": ["name"]}
        )
        
        # Verify
        self.mock_session.run.assert_called()


if __name__ == "__main__":
    # This allows running tests with uv
    unittest.main()

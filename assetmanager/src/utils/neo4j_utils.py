"""
Utility functions for interacting with Neo4j database.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Union

from neo4j import GraphDatabase, Transaction, basic_auth
from neo4j.exceptions import ServiceUnavailable

from src.utils.config import get_neo4j_credentials

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Class to handle Neo4j database connections and queries."""

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None, database: Optional[str] = None):
        """
        Initialize the Neo4j connection.
        
        If credentials are not provided, they will be loaded from config.
        """
        credentials = get_neo4j_credentials()
        self.uri = uri or credentials["uri"]
        self.user = user or credentials["user"]
        self.password = password or credentials["password"]
        self.database = database or credentials["database"]
        self.driver = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        """Connect to the Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=basic_auth(self.user, self.password)
            )
            # Test the connection
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j database at {self.uri}")
        except ServiceUnavailable as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
            self.driver = None

    def run_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Run a Cypher query and return the results.
        
        Args:
            query: The Cypher query to run
            params: Optional parameters for the query
            
        Returns:
            List[Dict[str, Any]]: The query results
        """
        if not self.driver:
            self.connect()
            
        results = []
        
        with self.driver.session(database=self.database) as session:
            result = session.run(query, params or {})
            results = [dict(record) for record in result]
            
        return results

    def execute_transaction(self, tx_function, *args, **kwargs):
        """
        Execute a transaction function.
        
        Args:
            tx_function: Function that takes a transaction as first argument
            *args: Additional arguments to pass to the function
            **kwargs: Additional keyword arguments to pass to the function
            
        Returns:
            The result of the transaction function
        """
        if not self.driver:
            self.connect()
            
        with self.driver.session(database=self.database) as session:
            return session.execute_write(tx_function, *args, **kwargs)

    def create_node(self, label: str, properties: Dict[str, Any]) -> str:
        """
        Create a node in the database.
        
        Args:
            label: The node label
            properties: The node properties
            
        Returns:
            str: The ID of the created node
        """
        def create_node_tx(tx: Transaction, label: str, properties: Dict[str, Any]) -> str:
            query = f"CREATE (n:{label} $props) RETURN id(n) as node_id"
            result = tx.run(query, props=properties)
            return result.single()["node_id"]
            
        return self.execute_transaction(create_node_tx, label, properties)

    def create_relationship(self, from_id: str, to_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a relationship between two nodes.
        
        Args:
            from_id: The ID of the source node
            to_id: The ID of the target node
            rel_type: The relationship type
            properties: Optional relationship properties
            
        Returns:
            str: The ID of the created relationship
        """
        def create_rel_tx(tx: Transaction, from_id: str, to_id: str, rel_type: str, properties: Optional[Dict[str, Any]]) -> str:
            query = f"""
            MATCH (a), (b) 
            WHERE id(a) = $from_id AND id(b) = $to_id 
            CREATE (a)-[r:{rel_type} $props]->(b) 
            RETURN id(r) as rel_id
            """
            result = tx.run(query, from_id=from_id, to_id=to_id, props=properties or {})
            return result.single()["rel_id"]
            
        return self.execute_transaction(create_rel_tx, from_id, to_id, rel_type, properties)

    def merge_node(self, label: str, unique_properties: Dict[str, Any], other_properties: Optional[Dict[str, Any]] = None) -> str:
        """
        Merge a node in the database (create if not exists, update if exists).
        
        Args:
            label: The node label
            unique_properties: Properties that uniquely identify the node
            other_properties: Optional additional properties to set
            
        Returns:
            str: The ID of the merged node
        """
        def merge_node_tx(tx: Transaction, label: str, unique_props: Dict[str, Any], other_props: Optional[Dict[str, Any]]) -> str:
            # Build property string for MERGE clause
            unique_props_str = ", ".join([f"n.{k} = ${k}" for k in unique_props.keys()])
            
            # Build SET clause for other properties
            set_clause = ""
            if other_props and len(other_props) > 0:
                set_clause = "SET " + ", ".join([f"n.{k} = ${k}" for k in other_props.keys()])
            
            # Combine all parameters
            all_params = {**unique_props}
            if other_props:
                all_params.update(other_props)
            
            query = f"""
            MERGE (n:{label})
            WHERE {unique_props_str}
            {set_clause}
            RETURN id(n) as node_id
            """
            
            result = tx.run(query, **all_params)
            return result.single()["node_id"]
            
        return self.execute_transaction(merge_node_tx, label, unique_properties, other_properties)
        
    def import_from_json(self, json_data: Union[str, Dict, List], import_type: str = "nodes"):
        """
        Import data from JSON into Neo4j.
        
        Args:
            json_data: JSON string or parsed JSON object
            import_type: Type of import ('nodes', 'relationships', 'both')
        """
        # Parse JSON string if needed
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data
            
        # Handle different import types
        if import_type == "nodes":
            if isinstance(data, list):
                for node in data:
                    label = node.pop("label", "Entity")
                    self.create_node(label, node)
            else:
                label = data.pop("label", "Entity")
                self.create_node(label, data)
                
        elif import_type == "relationships":
            if isinstance(data, list):
                for rel in data:
                    from_id = rel.pop("from_id")
                    to_id = rel.pop("to_id")
                    rel_type = rel.pop("type")
                    self.create_relationship(from_id, to_id, rel_type, rel)
            else:
                from_id = data.pop("from_id")
                to_id = data.pop("to_id")
                rel_type = data.pop("type")
                self.create_relationship(from_id, to_id, rel_type, data)
                
        elif import_type == "both":
            # This requires a specific format for the JSON
            if "nodes" in data and "relationships" in data:
                # First import nodes
                node_ids = {}
                for node in data["nodes"]:
                    node_key = node.pop("key", None)
                    label = node.pop("label", "Entity")
                    node_id = self.create_node(label, node)
                    if node_key:
                        node_ids[node_key] = node_id
                
                # Then import relationships
                for rel in data["relationships"]:
                    from_key = rel.pop("from_key")
                    to_key = rel.pop("to_key")
                    rel_type = rel.pop("type")
                    
                    if from_key in node_ids and to_key in node_ids:
                        self.create_relationship(node_ids[from_key], node_ids[to_key], rel_type, rel)
            else:
                raise ValueError("JSON format for 'both' import type must contain 'nodes' and 'relationships' keys")
        else:
            raise ValueError(f"Invalid import_type: {import_type}. Must be one of 'nodes', 'relationships', 'both'")


def cypher_query_from_natural_language(query: str, schema_info: Optional[str] = None) -> str:
    """
    Convert natural language to Cypher query using Vertex AI.
    This is a placeholder function that will be implemented separately.
    
    Args:
        query: Natural language query
        schema_info: Optional schema information to help with conversion
        
    Returns:
        str: The generated Cypher query
    """
    # This will be implemented in another module
    return "MATCH (n) RETURN n LIMIT 10"  # Placeholder

#!/usr/bin/env python
"""
Neo4j utilities for the Neo4j Generative AI Google Cloud project.

This module provides functionality for interacting with Neo4j databases,
including connection management, query execution, and vector operations.
"""

import logging
import socket
from typing import Dict, List, Any, Optional, Union, Tuple

from neo4j import GraphDatabase, Driver, Session, Result
from neo4j.exceptions import ServiceUnavailable, AuthError

from . import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Neo4jClient:
    """Client for interacting with Neo4j databases."""
    
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        """
        Initialize the Neo4j client.
        
        Args:
            uri: Neo4j connection URI (defaults to config.NEO4J_URI)
            user: Neo4j username (defaults to config.NEO4J_USER)
            password: Neo4j password (defaults to config.NEO4J_PASSWORD)
            database: Neo4j database name (defaults to config.NEO4J_DATABASE)
        """
        self.uri = uri or config.NEO4J_URI
        self.user = user or config.NEO4J_USER
        self.password = password or config.NEO4J_PASSWORD
        self.database = database or config.NEO4J_DATABASE
        
        if not self.uri or not self.user or not self.password:
            raise ValueError("Neo4j connection details (URI, user, password) must be provided")
        
        # Validate URI scheme
        if not self.uri.startswith(("neo4j://", "neo4j+s://", "bolt://", "bolt+s://")):
            raise ValueError(f"Invalid Neo4j URI scheme: {self.uri}. Must start with neo4j://, neo4j+s://, bolt://, or bolt+s://")
        
        # Extract hostname for DNS check
        hostname = self.uri.split("://")[1].split(":")[0]
        if hostname.endswith(".databases.neo4j.io"):
            # Verify DNS resolution for Neo4j Aura hostnames
            try:
                socket.gethostbyname(hostname)
            except socket.gaierror:
                raise ValueError(f"Cannot resolve Neo4j hostname: {hostname}. Check your network connection or DNS settings.")
        
        # Initialize driver
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
        )
        
        # Test connection
        try:
            self._test_connection()
            logger.info(f"Connected to Neo4j database at {self._mask_uri(self.uri)}")
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j database at {self._mask_uri(self.uri)}: {e}")
            raise
    
    def _mask_uri(self, uri: str) -> str:
        """
        Mask sensitive information in URI for logging.
        
        Args:
            uri: The URI to mask
            
        Returns:
            Masked URI with credentials removed
        """
        if "@" in uri:
            # URI contains credentials, mask them
            scheme, rest = uri.split("://", 1)
            if "@" in rest:
                credentials, host = rest.split("@", 1)
                return f"{scheme}://***:***@{host}"
        
        # No credentials in URI, return as is
        return uri
    
    def _test_connection(self) -> None:
        """
        Test the Neo4j connection.
        
        Raises:
            ServiceUnavailable: If the Neo4j server is unavailable
            AuthError: If authentication fails
        """
        with self.driver.session(database=self.database) as session:
            result = session.run("RETURN 1 AS test")
            record = result.single()
            if record["test"] != 1:
                raise ServiceUnavailable("Neo4j connection test failed")
    
    def close(self) -> None:
        """
Close the Neo4j driver connection.
        """
        if self.driver:
            self.driver.close()
            logger.info("Closed Neo4j connection")
    
    def run_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run a Cypher query and return the results.
        
        Args:
            query: The Cypher query to execute
            params: Query parameters (optional)
            database: Database name (defaults to self.database)
            
        Returns:
            List of records as dictionaries
        """
        db = database or self.database
        params = params or {}
        
        with self.driver.session(database=db) as session:
            result = session.run(query, params)
            records = [record.data() for record in result]
            
            logger.debug(f"Executed query: {query}")
            logger.debug(f"Query returned {len(records)} records")
            
            return records
    
    def run_query_single(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Run a Cypher query and return a single record.
        
        Args:
            query: The Cypher query to execute
            params: Query parameters (optional)
            database: Database name (defaults to self.database)
            
        Returns:
            Single record as dictionary or None if no records
        """
        records = self.run_query(query, params, database)
        return records[0] if records else None
    
    def create_node(
        self,
        labels: Union[str, List[str]],
        properties: Dict[str, Any],
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a node in the Neo4j database.
        
        Args:
            labels: Node label(s)
            properties: Node properties
            database: Database name (defaults to self.database)
            
        Returns:
            Created node as dictionary
        """
        # Convert single label to list
        if isinstance(labels, str):
            labels = [labels]
        
        # Build label string
        label_str = ":".join(labels)
        
        # Build query
        query = f"CREATE (n:{label_str} $props) RETURN n"
        params = {"props": properties}
        
        # Execute query
        result = self.run_query_single(query, params, database)
        
        return result["n"] if result else None
    
    def merge_node(
        self,
        labels: Union[str, List[str]],
        match_properties: Dict[str, Any],
        set_properties: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merge a node in the Neo4j database (create if not exists, update if exists).
        
        Args:
            labels: Node label(s)
            match_properties: Properties to match existing node
            set_properties: Properties to set on the node (optional)
            database: Database name (defaults to self.database)
            
        Returns:
            Merged node as dictionary
        """
        # Convert single label to list
        if isinstance(labels, str):
            labels = [labels]
        
        # Build label string
        label_str = ":".join(labels)
        
        # Build query
        query = f"MERGE (n:{label_str} $match_props)"
        
        # Add SET clause if set_properties provided
        if set_properties:
            query += " ON CREATE SET n += $set_props ON MATCH SET n += $set_props"
            params = {
                "match_props": match_properties,
                "set_props": set_properties,
            }
        else:
            params = {"match_props": match_properties}
        
        # Return node
        query += " RETURN n"
        
        # Execute query
        result = self.run_query_single(query, params, database)
        
        return result["n"] if result else None
    
    def create_relationship(
        self,
        start_node_labels: Union[str, List[str]],
        start_node_properties: Dict[str, Any],
        end_node_labels: Union[str, List[str]],
        end_node_properties: Dict[str, Any],
        relationship_type: str,
        relationship_properties: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a relationship between two nodes in the Neo4j database.
        
        Args:
            start_node_labels: Start node label(s)
            start_node_properties: Start node properties to match
            end_node_labels: End node label(s)
            end_node_properties: End node properties to match
            relationship_type: Relationship type
            relationship_properties: Relationship properties (optional)
            database: Database name (defaults to self.database)
            
        Returns:
            Created relationship as dictionary
        """
        # Convert single labels to lists
        if isinstance(start_node_labels, str):
            start_node_labels = [start_node_labels]
        
        if isinstance(end_node_labels, str):
            end_node_labels = [end_node_labels]
        
        # Build label strings
        start_label_str = ":".join(start_node_labels)
        end_label_str = ":".join(end_node_labels)
        
        # Build query
        query = f"""MATCH (a:{start_label_str}), (b:{end_label_str})
                  WHERE a = $start_props AND b = $end_props
                  CREATE (a)-[r:{relationship_type} $rel_props]->(b)
                  RETURN r"""
        
        # Set relationship properties
        rel_props = relationship_properties or {}
        
        # Set parameters
        params = {
            "start_props": start_node_properties,
            "end_props": end_node_properties,
            "rel_props": rel_props,
        }
        
        # Execute query
        result = self.run_query_single(query, params, database)
        
        return result["r"] if result else None
    
    def merge_relationship(
        self,
        start_node_labels: Union[str, List[str]],
        start_node_properties: Dict[str, Any],
        end_node_labels: Union[str, List[str]],
        end_node_properties: Dict[str, Any],
        relationship_type: str,
        relationship_properties: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merge a relationship between two nodes in the Neo4j database.
        
        Args:
            start_node_labels: Start node label(s)
            start_node_properties: Start node properties to match
            end_node_labels: End node label(s)
            end_node_properties: End node properties to match
            relationship_type: Relationship type
            relationship_properties: Relationship properties (optional)
            database: Database name (defaults to self.database)
            
        Returns:
            Merged relationship as dictionary
        """
        # Convert single labels to lists
        if isinstance(start_node_labels, str):
            start_node_labels = [start_node_labels]
        
        if isinstance(end_node_labels, str):
            end_node_labels = [end_node_labels]
        
        # Build label strings
        start_label_str = ":".join(start_node_labels)
        end_label_str = ":".join(end_node_labels)
        
        # Build query
        query = f"""MATCH (a:{start_label_str}), (b:{end_label_str})
                  WHERE a = $start_props AND b = $end_props
                  MERGE (a)-[r:{relationship_type}]->(b)"""
        
        # Add SET clause if relationship_properties provided
        if relationship_properties:
            query += " ON CREATE SET r += $rel_props ON MATCH SET r += $rel_props"
            params = {
                "start_props": start_node_properties,
                "end_props": end_node_properties,
                "rel_props": relationship_properties,
            }
        else:
            params = {
                "start_props": start_node_properties,
                "end_props": end_node_properties,
            }
        
        # Return relationship
        query += " RETURN r"
        
        # Execute query
        result = self.run_query_single(query, params, database)
        
        return result["r"] if result else None
    
    def create_vector_index(
        self,
        index_name: str,
        node_label: str,
        vector_property: str,
        dimensions: int,
        similarity_function: str = "cosine",
        database: Optional[str] = None,
    ) -> None:
        """
        Create a vector index in the Neo4j database.
        
        Args:
            index_name: Name of the vector index
            node_label: Label of nodes to index
            vector_property: Property containing vector embeddings
            dimensions: Dimensionality of the vectors
            similarity_function: Similarity function to use (cosine, euclidean, dot)
            database: Database name (defaults to self.database)
        """
        # Validate similarity function
        valid_functions = ["cosine", "euclidean", "dot"]
        if similarity_function not in valid_functions:
            raise ValueError(f"Invalid similarity function: {similarity_function}. Must be one of {valid_functions}")
        
        # Build query
        query = f"""CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                  FOR (n:{node_label})
                  ON n.{vector_property}
                  OPTIONS {{
                      indexConfig: {{
                          `vector.dimensions`: {dimensions},
                          `vector.similarity_function`: '{similarity_function}'
                      }}
                  }}"""
        
        # Execute query
        self.run_query(query, database=database)
        
        logger.info(f"Created vector index {index_name} on :{node_label}.{vector_property}")
    
    def drop_vector_index(
        self,
        index_name: str,
        database: Optional[str] = None,
    ) -> None:
        """
        Drop a vector index from the Neo4j database.
        
        Args:
            index_name: Name of the vector index to drop
            database: Database name (defaults to self.database)
        """
        # Build query
        query = f"DROP INDEX {index_name} IF EXISTS"
        
        # Execute query
        self.run_query(query, database=database)
        
        logger.info(f"Dropped vector index {index_name}")
    
    def list_vector_indexes(
        self,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all vector indexes in the Neo4j database.
        
        Args:
            database: Database name (defaults to self.database)
            
        Returns:
            List of vector indexes as dictionaries
        """
        # Build query
        query = """SHOW INDEXES
                  YIELD name, type, labelsOrTypes, properties, options
                  WHERE type = 'VECTOR'
                  RETURN name, labelsOrTypes, properties, options"""
        
        # Execute query
        results = self.run_query(query, database=database)
        
        return results
    
    def vector_search(
        self,
        node_label: str,
        vector_property: str,
        query_vector: List[float],
        limit: int = 10,
        similarity_cutoff: Optional[float] = None,
        additional_filters: Optional[str] = None,
        return_fields: Optional[List[str]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform a vector similarity search in the Neo4j database.
        
        Args:
            node_label: Label of nodes to search
            vector_property: Property containing vector embeddings
            query_vector: Query vector for similarity search
            limit: Maximum number of results to return
            similarity_cutoff: Minimum similarity score (0-1) to include in results
            additional_filters: Additional Cypher WHERE clause filters
            return_fields: Node properties to return (defaults to all)
            database: Database name (defaults to self.database)
            
        Returns:
            List of matching nodes with similarity scores
        """
        # Build WHERE clause
        where_clause = ""
        if additional_filters:
            where_clause = f"WHERE {additional_filters}"
        
        # Build RETURN clause
        if return_fields:
            return_fields_str = ", ".join([f"n.{field} AS {field}" for field in return_fields])
            return_clause = f"RETURN n, {return_fields_str}, similarity AS score"
        else:
            return_clause = "RETURN n, similarity AS score"
        
        # Build similarity cutoff
        cutoff_clause = ""
        if similarity_cutoff is not None:
            cutoff_clause = f"WHERE similarity >= {similarity_cutoff}"
        
        # Build query
        query = f"""MATCH (n:{node_label})
                  {where_clause}
                  WITH n, vector.similarity(n.{vector_property}, $query_vector) AS similarity
                  {cutoff_clause}
                  ORDER BY similarity DESC
                  LIMIT {limit}
                  {return_clause}"""
        
        # Execute query
        params = {"query_vector": query_vector}
        results = self.run_query(query, params, database)
        
        return results
    
    def create_constraint(
        self,
        constraint_name: str,
        node_label: str,
        property_name: str,
        constraint_type: str = "UNIQUE",
        database: Optional[str] = None,
    ) -> None:
        """
        Create a constraint in the Neo4j database.
        
        Args:
            constraint_name: Name of the constraint
            node_label: Label of nodes to constrain
            property_name: Property to constrain
            constraint_type: Type of constraint (UNIQUE, EXISTS, etc.)
            database: Database name (defaults to self.database)
        """
        # Validate constraint type
        valid_types = ["UNIQUE", "EXISTS"]
        if constraint_type not in valid_types:
            raise ValueError(f"Invalid constraint type: {constraint_type}. Must be one of {valid_types}")
        
        # Build query
        if constraint_type == "UNIQUE":
            query = f"""CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
                      FOR (n:{node_label})
                      REQUIRE n.{property_name} IS UNIQUE"""
        else:  # EXISTS
            query = f"""CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
                      FOR (n:{node_label})
                      REQUIRE n.{property_name} IS NOT NULL"""
        
        # Execute query
        self.run_query(query, database=database)
        
        logger.info(f"Created {constraint_type} constraint {constraint_name} on :{node_label}.{property_name}")
    
    def drop_constraint(
        self,
        constraint_name: str,
        database: Optional[str] = None,
    ) -> None:
        """
        Drop a constraint from the Neo4j database.
        
        Args:
            constraint_name: Name of the constraint to drop
            database: Database name (defaults to self.database)
        """
        # Build query
        query = f"DROP CONSTRAINT {constraint_name} IF EXISTS"
        
        # Execute query
        self.run_query(query, database=database)
        
        logger.info(f"Dropped constraint {constraint_name}")
    
    def list_constraints(
        self,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all constraints in the Neo4j database.
        
        Args:
            database: Database name (defaults to self.database)
            
        Returns:
            List of constraints as dictionaries
        """
        # Build query
        query = """SHOW CONSTRAINTS
                  YIELD name, type, labelsOrTypes, properties
                  RETURN name, type, labelsOrTypes, properties"""
        
        # Execute query
        results = self.run_query(query, database=database)
        
        return results
    
    def __enter__(self) -> 'Neo4jClient':
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.close()

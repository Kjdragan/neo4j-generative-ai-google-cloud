"""
Neo4j Uploader module for interacting with a Neo4j database.

This module provides functionality to:
- Connect to a Neo4j instance (AuraDB or local).
- Upload extracted entities as nodes.
- Create relationships between nodes.
- Store text embeddings associated with nodes or text chunks.
- Create and manage vector indexes for similarity search.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple

from neo4j import GraphDatabase, Driver, unit_of_work
from neo4j.exceptions import ServiceUnavailable, Neo4jError

logger = logging.getLogger(__name__)

class Neo4jUploader:
    """
    Handles connections and data uploads to a Neo4j database.
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize the Neo4jUploader.

        Args:
            uri: URI for the Neo4j database (e.g., "neo4j+s://xxxx.databases.neo4j.io").
            user: Username for Neo4j authentication.
            password: Password for Neo4j authentication.
        """
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: Optional[Driver] = None
        self._connect()

    def _connect(self) -> None:
        """Establish a connection to the Neo4j database."""
        try:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self._driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j at {self.uri}")
        except ServiceUnavailable as e:
            logger.error(f"Could not connect to Neo4j at {self.uri}: {e}", exc_info=True)
            self._driver = None # Ensure driver is None if connection fails
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during Neo4j connection: {e}", exc_info=True)
            self._driver = None
            raise

    def close(self) -> None:
        """Close the Neo4j database connection."""
        if self._driver is not None:
            self._driver.close()
            logger.info("Neo4j connection closed.")

    @property
    def driver(self) -> Driver:
        """Provides access to the Neo4j driver, ensuring it's connected."""
        if self._driver is None:
            logger.warning("Neo4j driver was not initialized. Attempting to reconnect.")
            self._connect() # Attempt to reconnect if driver is None
            if self._driver is None: # If still None after reconnect attempt
                 raise ConnectionError("Failed to connect to Neo4j. Driver is not available.")
        return self._driver

    @staticmethod
    @unit_of_work(timeout=30) # Example timeout for transactions
    def _execute_query(tx, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Helper function to execute a Cypher query within a transaction."""
        result = tx.run(query, parameters or {})
        return [record.data() for record in result]

    def run_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute an arbitrary Cypher query.

        Args:
            query: The Cypher query string.
            parameters: A dictionary of parameters for the query.

        Returns:
            A list of dictionaries, where each dictionary represents a result record.
        """
        try:
            with self.driver.session() as session:
                results = session.execute_write(self._execute_query, query, parameters)
                return results
        except Neo4jError as e:
            logger.error(f"Error executing Cypher query: {query} with params {parameters}. Error: {e}", exc_info=True)
            raise
        except ConnectionError as e: # Catch ConnectionError if driver is unavailable
            logger.error(f"Neo4j connection error during query execution: {e}", exc_info=True)
            raise

    def add_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adds a new node to the graph or merges if a unique property matches.
        Assumes a unique constraint on 'id' or 'name' property for merging if provided.
        
        Args:
            label: The label for the node (e.g., "Person", "Company").
            properties: A dictionary of properties for the node.

        Returns:
            The properties of the created or merged node.
        """
        # Prioritize 'id' for uniqueness, then 'name', otherwise create new.
        unique_key = None
        if 'id' in properties:
            unique_key = 'id'
        elif 'name' in properties:
            unique_key = 'name'

        if unique_key:
            query = (
                f"MERGE (n:{label} {{{unique_key}: $props.{unique_key}}}) "
                f"ON CREATE SET n = $props, n.created_at = timestamp() "
                f"ON MATCH SET n += $props, n.updated_at = timestamp() "
                f"RETURN properties(n) as node"
            )
        else:
            query = (
                f"CREATE (n:{label} $props) "
                f"SET n.created_at = timestamp() "
                f"RETURN properties(n) as node"
            )
        
        result = self.run_query(query, {"props": properties})
        return result[0]["node"] if result else {}

    def add_relationship(
        self,
        start_node_label: str,
        start_node_properties: Dict[str, Any], # Properties to match start node (e.g., {'name': 'Alice'})
        end_node_label: str,
        end_node_properties: Dict[str, Any],   # Properties to match end node (e.g., {'name': 'Bob'})
        relationship_type: str,
        relationship_properties: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Adds a relationship between two existing nodes.
        Nodes are matched based on a key property (e.g., 'id' or 'name').

        Args:
            start_node_label: Label of the start node.
            start_node_properties: Dictionary to identify the start node (e.g., {'id': '123'}).
            end_node_label: Label of the end node.
            end_node_properties: Dictionary to identify the end node (e.g., {'id': '456'}).
            relationship_type: Type of the relationship (e.g., "KNOWS").
            relationship_properties: Optional properties for the relationship.

        Returns:
            Properties of the created relationship, or None if unsuccessful.
        """
        # Determine match keys (e.g. if 'id' is present use it, else 'name')
        start_match_key = 'id' if 'id' in start_node_properties else 'name'
        end_match_key = 'id' if 'id' in end_node_properties else 'name'

        if not start_match_key in start_node_properties or not end_match_key in end_node_properties:
            logger.error("Start or end node properties missing required match key ('id' or 'name').")
            return None

        query = (
            f"MATCH (a:{start_node_label} {{{start_match_key}: $start_props.{start_match_key}}}) "
            f"MATCH (b:{end_node_label} {{{end_match_key}: $end_props.{end_match_key}}}) "
            f"MERGE (a)-[r:{relationship_type}]->(b) "
            f"ON CREATE SET r = $rel_props, r.created_at = timestamp() "
            f"ON MATCH SET r += $rel_props, r.updated_at = timestamp() "
            f"RETURN properties(r) as relationship"
        )
        params = {
            "start_props": start_node_properties,
            "end_props": end_node_properties,
            "rel_props": relationship_properties or {}
        }
        result = self.run_query(query, params)
        return result[0]["relationship"] if result else None

    def add_chunk_with_embedding(
        self,
        document_id: str, # ID of the parent document
        chunk_id: str,    # Unique ID for this chunk
        text_chunk: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Adds a text chunk node with its embedding and connects it to a parent Document node.
        Assumes a Document node with the given document_id already exists or can be merged.

        Args:
            document_id: Identifier for the parent document.
            chunk_id: Unique identifier for this text chunk.
            text_chunk: The text content of the chunk.
            embedding: The embedding vector for the text chunk.
            metadata: Optional additional properties for the Chunk node.

        Returns:
            Properties of the created Chunk node.
        """
        chunk_props = {
            "id": chunk_id,
            "text": text_chunk,
            "embedding": embedding,
            "document_id": document_id,
            **(metadata or {})
        }
        
        # Merge Document node (create if not exists)
        # This assumes Document nodes are identified by 'id'
        merge_doc_query = (
            f"MERGE (d:Document {{id: $doc_id}}) "
            f"ON CREATE SET d.created_at = timestamp() "
            f"RETURN d"
        )
        self.run_query(merge_doc_query, {"doc_id": document_id})

        # Create Chunk node and relationship to Document
        query = (
            f"MATCH (d:Document {{id: $doc_id}}) "
            f"CREATE (c:Chunk $chunk_props) "
            f"CREATE (d)-[:HAS_CHUNK]->(c) "
            f"RETURN properties(c) as chunk"
        )
        params = {"doc_id": document_id, "chunk_props": chunk_props}
        result = self.run_query(query, params)
        return result[0]["chunk"] if result else {}

    def create_vector_index(
        self,
        index_name: str,
        node_label: str, 
        embedding_property: str,
        dimensions: int,
        similarity_function: str = "cosine" # e.g., "cosine", "euclidean"
    ) -> None:
        """
        Creates a vector index in Neo4j (requires Neo4j 5.11+ or Aura).

        Args:
            index_name: Name for the vector index.
            node_label: The node label to index (e.g., "Chunk").
            embedding_property: The property storing the embedding vector (e.g., "embedding").
            dimensions: The dimensionality of the embedding vectors.
            similarity_function: The similarity function to use ('cosine' or 'euclidean').
        """
        # Check if index already exists
        check_query = "SHOW INDEXES WHERE name = $index_name"
        existing_indexes = self.run_query(check_query, {"index_name": index_name})
        if existing_indexes and any(idx.get('name') == index_name for idx in existing_indexes):
            logger.info(f"Vector index '{index_name}' already exists.")
            return

        query = (
            f"CREATE VECTOR INDEX {index_name} "
            f"IF NOT EXISTS " # Ensures idempotency if check above is insufficient due to timing
            f"FOR (n:{node_label}) ON (n.{embedding_property}) "
            f"OPTIONS {{indexConfig: {{`vector.dimensions`: {dimensions}, `vector.similarity_function`: '{similarity_function}'}}}}"
        )
        try:
            self.run_query(query)
            logger.info(f"Successfully created vector index '{index_name}' on {node_label}({embedding_property}).")
        except Neo4jError as e:
            # Common error: Vector index creation might not be supported or enterprise feature
            if "SyntaxError" in str(e) or "Unsupported administration command" in str(e):
                 logger.warning(f"Could not create vector index '{index_name}'. This Neo4j version/edition might not support 'CREATE VECTOR INDEX'. Error: {e}")
            else:
                logger.error(f"Failed to create vector index '{index_name}': {e}", exc_info=True)
                raise

    def vector_search(
        self,
        index_name: str,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Performs a vector similarity search using a pre-built index.

        Args:
            index_name: The name of the vector index to query.
            query_embedding: The embedding vector to search for.
            top_k: The number of nearest neighbors to return.

        Returns:
            A list of dictionaries, each containing the node properties and similarity score.
        """
        query = (
            f"CALL db.index.vector.queryNodes($index_name, $top_k, $embedding) "
            f"YIELD node, score "
            f"RETURN properties(node) as item, score"
        )
        params = {"index_name": index_name, "top_k": top_k, "embedding": query_embedding}
        try:
            return self.run_query(query, params)
        except Neo4jError as e:
            if "NoSuchIndexException" in str(e) or "ProcedureNotFoundException" in str(e):
                logger.error(f"Vector search failed. Index '{index_name}' may not exist or vector search procedures are unavailable. Error: {e}")
                return []
            logger.error(f"Error during vector search on index '{index_name}': {e}", exc_info=True)
            raise

# Example Usage (for testing or demonstration)
if __name__ == '__main__':
    # This example assumes you have a Neo4j instance running (e.g., AuraDB or local Docker).
    # Set these environment variables or replace with your actual credentials.
    import os
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = os.getenv("NEO4J_USERNAME")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        print("Please set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD environment variables.")
    else:
        print(f"Connecting to Neo4j at {NEO4J_URI}...")
        try:
            uploader = Neo4jUploader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

            # 1. Add some nodes
            print("\n--- Adding Nodes ---")
            person1 = uploader.add_node("Person", {"name": "Alice", "age": 30, "id": "p1"})
            print(f"Added/Merged Person: {person1}")
            person2 = uploader.add_node("Person", {"name": "Bob", "age": 25, "id": "p2"})
            print(f"Added/Merged Person: {person2}")
            company1 = uploader.add_node("Company", {"name": "Neo4j Inc.", "id": "c1"})
            print(f"Added/Merged Company: {company1}")

            # 2. Add relationships
            print("\n--- Adding Relationships ---")
            rel1 = uploader.add_relationship("Person", {"id": "p1"}, "Person", {"id": "p2"}, "KNOWS", {"since": 2020})
            print(f"Added Relationship: {rel1}")
            rel2 = uploader.add_relationship("Person", {"id": "p1"}, "Company", {"id": "c1"}, "WORKS_FOR", {"role": "Engineer"})
            print(f"Added Relationship: {rel2}")

            # 3. Add document, chunk, and embedding
            print("\n--- Adding Document, Chunk, and Embedding ---")
            doc_id = "doc001"
            chunk_id = "chunk001_01"
            text = "This is a sample text chunk about Neo4j and vector search."
            # Example embedding (replace with actual embedding)
            embedding_vector = [0.1] * 128 # Placeholder, replace with actual 128-dim embedding
            
            chunk_node = uploader.add_chunk_with_embedding(doc_id, chunk_id, text, embedding_vector, {"source": "example_file.txt"})
            print(f"Added Chunk: {chunk_node}")

            # 4. Create vector index (ensure your Neo4j version supports this)
            print("\n--- Creating Vector Index ---")
            INDEX_NAME = "document_chunk_embeddings"
            NODE_LABEL = "Chunk"
            EMBEDDING_PROPERTY = "embedding"
            DIMENSIONS = len(embedding_vector) # Get dimensions from your actual embeddings
            uploader.create_vector_index(INDEX_NAME, NODE_LABEL, EMBEDDING_PROPERTY, DIMENSIONS)

            # 5. Perform vector search (requires index to be populated and ready)
            print("\n--- Performing Vector Search ---")
            # Wait a bit for the index to populate if creating it just now
            import time
            print("Waiting a few seconds for index to populate...")
            time.sleep(5) 
            
            query_vec = [0.11] * DIMENSIONS # Slightly different vector for query
            search_results = uploader.vector_search(INDEX_NAME, query_vec, top_k=1)
            if search_results:
                print(f"Found {len(search_results)} similar items:")
                for res in search_results:
                    print(f"  Item: {res['item'].get('text', 'N/A')}, Score: {res['score']:.4f}")
            else:
                print("No results found or search failed.")

            uploader.close()

        except ConnectionError as ce:
            print(f"Neo4j Connection Error: {ce}")
        except Neo4jError as ne:
            print(f"A Neo4j specific error occurred: {ne}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            logger.error("Neo4j Uploader example failed", exc_info=True)

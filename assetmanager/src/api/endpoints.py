"""
API endpoints for the Neo4j Asset Manager application.
"""
import json
import logging
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.models.nl_to_cypher import natural_language_to_cypher
from src.utils.neo4j_utils import Neo4jConnection

logger = logging.getLogger(__name__)

# Models
class CypherRequest(BaseModel):
    """Request model for Cypher query conversion."""
    query: str = Field(..., description="Natural language query to convert to Cypher")


class CypherResponse(BaseModel):
    """Response model for Cypher query conversion."""
    query: str = Field(..., description="Original natural language query")
    cypher: str = Field(..., description="Generated Cypher query")


class QueryRequest(BaseModel):
    """Request model for executing a query."""
    cypher: str = Field(..., description="Cypher query to execute")


class QueryResponse(BaseModel):
    """Response model for query execution."""
    result: List[Dict] = Field(..., description="Query result")
    execution_time: float = Field(..., description="Query execution time in milliseconds")


# Router
router = APIRouter(prefix="/api", tags=["API"])


# Get Neo4j connection
def get_neo4j_connection():
    """Get Neo4j connection as a dependency."""
    connection = Neo4jConnection()
    try:
        connection.connect()
        yield connection
    finally:
        connection.close()


@router.post("/natural-language-to-cypher", response_model=CypherResponse)
def convert_nl_to_cypher(
    request: CypherRequest,
    neo4j: Neo4jConnection = Depends(get_neo4j_connection),
):
    """Convert natural language to Cypher query."""
    try:
        cypher = natural_language_to_cypher(request.query, neo4j)
        return CypherResponse(query=request.query, cypher=cypher)
    except Exception as e:
        logger.error(f"Error converting query to Cypher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-query", response_model=QueryResponse)
def execute_query(
    request: QueryRequest,
    neo4j: Neo4jConnection = Depends(get_neo4j_connection),
):
    """Execute a Cypher query."""
    import time
    
    try:
        start_time = time.time()
        result = neo4j.run_query(request.cypher)
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        return QueryResponse(result=result, execution_time=execution_time)
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema")
def get_schema(
    neo4j: Neo4jConnection = Depends(get_neo4j_connection),
):
    """Get the database schema."""
    try:
        # Get node labels
        node_labels_query = "CALL db.labels()"
        node_labels = [record["label"] for record in neo4j.run_query(node_labels_query)]
        
        # Get relationship types
        rel_types_query = "CALL db.relationshipTypes()"
        rel_types = [record["relationshipType"] for record in neo4j.run_query(rel_types_query)]
        
        # Get property keys
        property_keys_query = "CALL db.propertyKeys()"
        property_keys = [record["propertyKey"] for record in neo4j.run_query(property_keys_query)]
        
        # Get more detailed schema information
        schema = {
            "node_labels": node_labels,
            "relationship_types": rel_types,
            "property_keys": property_keys,
            "nodes": {},
            "relationships": [],
        }
        
        # Get properties for each node type
        for label in node_labels:
            properties_query = f"""
            MATCH (n:{label})
            RETURN keys(n) AS props
            LIMIT 1
            """
            result = neo4j.run_query(properties_query)
            if result:
                props = result[0].get("props", [])
                schema["nodes"][label] = props
        
        # Get relationship details
        for rel_type in rel_types:
            rel_query = f"""
            MATCH ()-[r:{rel_type}]->()
            RETURN DISTINCT labels(startNode(r))[0] AS from, labels(endNode(r))[0] AS to, keys(r) AS props
            LIMIT 1
            """
            result = neo4j.run_query(rel_query)
            if result:
                from_label = result[0].get("from", "Unknown")
                to_label = result[0].get("to", "Unknown")
                props = result[0].get("props", [])
                schema["relationships"].append({
                    "type": rel_type,
                    "from": from_label,
                    "to": to_label,
                    "properties": props,
                })
        
        return schema
    except Exception as e:
        logger.error(f"Error getting schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Create FastAPI app
def create_app() -> FastAPI:
    """Create FastAPI app with API endpoints."""
    app = FastAPI(
        title="Neo4j Asset Manager API",
        description="API for Neo4j Asset Manager",
        version="1.0.0",
    )
    
    app.include_router(router)
    
    return app


# Standalone app
app = create_app()

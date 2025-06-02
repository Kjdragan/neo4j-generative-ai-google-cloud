"""
Natural language to Cypher conversion module.
Uses Gemini 2.5 Pro Preview to convert natural language queries to Cypher.
"""
import logging
import os
from typing import Dict, List, Optional, Union

from src.utils.config import get_gcp_settings
from src.utils.genai_utils import generate_text, GEMINI_LLM_MODEL

logger = logging.getLogger(__name__)

# Schema template to be populated with actual schema
SCHEMA_TEMPLATE = """
This Neo4j graph database contains the following node types and relationships:

Node Types:
{node_types}

Relationships:
{relationships}

Properties:
{properties}
"""

# Prompt template for converting natural language to Cypher
NL_TO_CYPHER_TEMPLATE = """
You are an expert in Neo4j and the Cypher query language. Your task is to convert natural language questions into Cypher queries based on the schema provided below.

{schema}

Guidelines:
1. Generate only valid Cypher queries that will run successfully against the given schema
2. Include any necessary pattern matching, filtering, and ordering
3. Return only data that answers the question
4. Use appropriate aliases for readability
5. For questions about connections or paths, use appropriate graph traversal
6. Apply LIMIT clauses when retrieving large sets of data
7. Return ONLY the Cypher query without any explanation or comments
8. Do not include any explanations in the query itself or as comments
9. The output should only be the pure Cypher query, without any markdown formatting or backticks

Natural language question: {question}

Cypher query:
"""


def get_database_schema(neo4j_connection) -> Dict[str, List[str]]:
    """
    Get the database schema from Neo4j.
    
    Args:
        neo4j_connection: Neo4j connection object
        
    Returns:
        Dict[str, List[str]]: Dictionary containing node types, relationships, and properties
    """
    # Get node labels
    node_labels_query = "CALL db.labels()"
    node_labels = [record["label"] for record in neo4j_connection.run_query(node_labels_query)]
    
    # Get relationship types
    rel_types_query = "CALL db.relationshipTypes()"
    rel_types = [record["relationshipType"] for record in neo4j_connection.run_query(rel_types_query)]
    
    # Get property keys
    property_keys_query = "CALL db.propertyKeys()"
    property_keys = [record["propertyKey"] for record in neo4j_connection.run_query(property_keys_query)]
    
    # Get more detailed schema information
    schema = {
        "node_types": [],
        "relationships": [],
        "properties": {}
    }
    
    # Get properties for each node type
    for label in node_labels:
        properties_query = f"""
        MATCH (n:{label})
        RETURN keys(n) AS props
        LIMIT 1
        """
        result = neo4j_connection.run_query(properties_query)
        if result:
            props = result[0].get("props", [])
            schema["node_types"].append(f"- {label}: {', '.join(props)}")
            schema["properties"][label] = props
    
    # Get relationship details
    for rel_type in rel_types:
        rel_query = f"""
        MATCH ()-[r:{rel_type}]->()
        RETURN DISTINCT labels(startNode(r))[0] AS from, labels(endNode(r))[0] AS to, keys(r) AS props
        LIMIT 1
        """
        result = neo4j_connection.run_query(rel_query)
        if result:
            from_label = result[0].get("from", "Unknown")
            to_label = result[0].get("to", "Unknown")
            props = result[0].get("props", [])
            schema["relationships"].append(
                f"- {from_label}-[:{rel_type} {{{', '.join(props)}}}]->{to_label}"
            )
    
    return schema


def format_schema_for_prompt(schema: Dict[str, List[str]]) -> str:
    """
    Format the schema for inclusion in the prompt.
    
    Args:
        schema: Schema dictionary
        
    Returns:
        str: Formatted schema string
    """
    node_types_str = "\n".join(schema["node_types"])
    relationships_str = "\n".join(schema["relationships"])
    
    # Format properties
    properties_list = []
    for node_type, props in schema["properties"].items():
        properties_list.append(f"- {node_type}: {', '.join(props)}")
    properties_str = "\n".join(properties_list)
    
    return SCHEMA_TEMPLATE.format(
        node_types=node_types_str,
        relationships=relationships_str,
        properties=properties_str
    )


def natural_language_to_cypher(
    question: str,
    neo4j_connection,
    model_name: str = GEMINI_LLM_MODEL,
    temperature: float = 0.1,
) -> str:
    """
    Convert a natural language question to a Cypher query.
    
    Args:
        question: The natural language question
        neo4j_connection: Neo4j connection object
        model_name: The model to use
        temperature: Temperature for generation
        
    Returns:
        str: The generated Cypher query
    """
    # Get database schema
    schema = get_database_schema(neo4j_connection)
    formatted_schema = format_schema_for_prompt(schema)
    
    # Generate Cypher query
    prompt = NL_TO_CYPHER_TEMPLATE.format(
        schema=formatted_schema,
        question=question
    )
    
    # Get GCP settings for the GenAI SDK
    gcp_settings = get_gcp_settings()
    
    cypher_query = generate_text(
        prompt=prompt,
        temperature=temperature,
        model_name=model_name,
        project_id=gcp_settings.get('project'),
        location=gcp_settings.get('location'),
        system_instruction="You are a Neo4j Cypher query generation expert. Generate valid Cypher queries based on natural language questions and schema information."
    )
    
    # Clean up the query
    cypher_query = cypher_query.strip()
    if cypher_query.startswith('```') and cypher_query.endswith('```'):
        cypher_query = cypher_query[3:-3].strip()
    
    logger.info(f"Generated Cypher query: {cypher_query}")
    
    return cypher_query

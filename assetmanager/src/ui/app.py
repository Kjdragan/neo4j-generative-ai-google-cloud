"""
Streamlit application for Neo4j Asset Manager.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_chat import message

from src.models.nl_to_cypher import natural_language_to_cypher
from src.utils.config import get_gcp_settings, get_neo4j_credentials
from src.utils.neo4j_utils import Neo4jConnection
from src.utils.vertex_ai import generate_text, init_vertex_ai

# Configure page
st.set_page_config(
    page_title="Neo4j Asset Manager",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "neo4j_connection" not in st.session_state:
    st.session_state.neo4j_connection = None
    
if "cypher_history" not in st.session_state:
    st.session_state.cypher_history = []


def initialize_connections():
    """Initialize connections to Neo4j and Vertex AI."""
    if st.session_state.neo4j_connection is None:
        # Initialize Neo4j connection
        neo4j_credentials = get_neo4j_credentials()
        st.session_state.neo4j_connection = Neo4jConnection(
            uri=neo4j_credentials["uri"],
            user=neo4j_credentials["user"],
            password=neo4j_credentials["password"],
            database=neo4j_credentials["database"],
        )
        st.session_state.neo4j_connection.connect()
        
        # Initialize Vertex AI
        init_vertex_ai()


def display_header():
    """Display the application header."""
    st.title("Neo4j Asset Manager")
    st.markdown(
        """
        This application uses Google Cloud Vertex AI Gemini models to query a Neo4j database 
        containing SEC EDGAR Form-13 data. Simply enter your question in natural language, 
        and the application will convert it to a Cypher query and retrieve the results.
        """
    )
    
    # Display connection information
    with st.expander("Connection Information"):
        gcp_settings = get_gcp_settings()
        neo4j_credentials = get_neo4j_credentials()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("GCP Settings")
            st.markdown(f"**Project:** {gcp_settings['project']}")
            st.markdown(f"**Location:** {gcp_settings['location']}")
            st.markdown(f"**LLM Model:** {gcp_settings['llm_model']}")
            st.markdown(f"**Embedding Model:** {gcp_settings['embedding_model']}")
            
        with col2:
            st.subheader("Neo4j Connection")
            st.markdown(f"**URI:** {neo4j_credentials['uri']}")
            st.markdown(f"**User:** {neo4j_credentials['user']}")
            st.markdown(f"**Database:** {neo4j_credentials['database']}")


def display_chat_interface():
    """Display the chat interface."""
    st.subheader("Chat Interface")
    
    # Display previous messages
    for i, (role, content) in enumerate(st.session_state.messages):
        message(content, is_user=(role == "user"), key=f"{role}_{i}")
    
    # Input for new message
    user_input = st.chat_input("Ask a question about the SEC EDGAR data...")
    
    if user_input:
        # Add user message to chat history
        st.session_state.messages.append(("user", user_input))
        
        # Display user message
        message(user_input, is_user=True, key=f"user_{len(st.session_state.messages)}")
        
        # Process user input
        try:
            # Convert natural language to Cypher
            cypher = natural_language_to_cypher(user_input, st.session_state.neo4j_connection)
            
            # Add Cypher query to history
            st.session_state.cypher_history.append(cypher)
            
            # Execute Cypher query
            results = st.session_state.neo4j_connection.run_query(cypher)
            
            # Create response
            if results:
                # Format results
                response = format_results(results)
            else:
                response = "No results found for your query."
            
            # Add system message with response
            st.session_state.messages.append(("assistant", response))
            
            # Display system message
            message(response, is_user=False, key=f"assistant_{len(st.session_state.messages)}")
            
        except Exception as e:
            # Add error message
            error_message = f"Error: {str(e)}"
            st.session_state.messages.append(("assistant", error_message))
            
            # Display error message
            message(error_message, is_user=False, key=f"assistant_{len(st.session_state.messages)}")
            

def format_results(results: List[Dict[str, Any]]) -> str:
    """
    Format query results for display.
    
    Args:
        results: The query results
        
    Returns:
        str: The formatted results
    """
    # Check if results contain numeric data that could be visualized
    numeric_columns = []
    for key in results[0].keys():
        if all(isinstance(result.get(key), (int, float)) for result in results):
            numeric_columns.append(key)
    
    # Generate response text
    if len(results) == 1:
        # Single result
        response = "Here's what I found:\n\n"
        for key, value in results[0].items():
            response += f"**{key}**: {value}\n"
    else:
        # Multiple results
        response = f"I found {len(results)} results:\n\n"
        
        # Create a table for display
        table_data = []
        for i, result in enumerate(results[:10]):  # Limit to 10 results for display
            row = {k: str(v)[:100] + "..." if isinstance(v, str) and len(str(v)) > 100 else v 
                  for k, v in result.items()}
            table_data.append(row)
        
        # Convert to Markdown table
        if table_data:
            df = pd.DataFrame(table_data)
            response += df.to_markdown(index=False)
            
            if len(results) > 10:
                response += f"\n\n*Showing 10 of {len(results)} results*"
    
    return response


def display_cypher_history():
    """Display the Cypher query history."""
    st.subheader("Cypher Query History")
    
    if not st.session_state.cypher_history:
        st.info("No Cypher queries have been executed yet.")
        return
    
    for i, cypher in enumerate(st.session_state.cypher_history):
        with st.expander(f"Query {i+1}"):
            st.code(cypher, language="cypher")
            
            # Button to re-run query
            if st.button(f"Re-run Query {i+1}"):
                try:
                    results = st.session_state.neo4j_connection.run_query(cypher)
                    
                    if results:
                        # Display results
                        st.subheader("Results")
                        st.dataframe(results)
                    else:
                        st.info("No results found for this query.")
                except Exception as e:
                    st.error(f"Error executing query: {str(e)}")


def display_visualization():
    """Display visualization options."""
    st.subheader("Visualization")
    
    # Only show visualization options if there are executed queries
    if not st.session_state.cypher_history:
        st.info("Execute a query to enable visualization options.")
        return
    
    # Select query to visualize
    selected_query_index = st.selectbox(
        "Select a query to visualize",
        range(len(st.session_state.cypher_history)),
        format_func=lambda i: f"Query {i+1}",
    )
    
    selected_query = st.session_state.cypher_history[selected_query_index]
    
    # Execute selected query
    try:
        results = st.session_state.neo4j_connection.run_query(selected_query)
        
        if not results:
            st.info("No results to visualize for this query.")
            return
        
        # Convert results to DataFrame
        df = pd.DataFrame(results)
        
        # Show available columns
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_columns = df.select_dtypes(include=["object"]).columns.tolist()
        
        if not numeric_columns:
            st.warning("No numeric columns available for visualization.")
            return
        
        # Create visualization options
        viz_type = st.selectbox(
            "Select visualization type",
            ["Bar Chart", "Line Chart", "Scatter Plot", "Pie Chart"],
        )
        
        if viz_type == "Bar Chart":
            x_column = st.selectbox("Select X-axis column", categorical_columns)
            y_column = st.selectbox("Select Y-axis column", numeric_columns)
            
            fig = px.bar(df, x=x_column, y=y_column, title=f"{y_column} by {x_column}")
            st.plotly_chart(fig, use_container_width=True)
            
        elif viz_type == "Line Chart":
            x_column = st.selectbox("Select X-axis column", df.columns.tolist())
            y_column = st.selectbox("Select Y-axis column", numeric_columns)
            
            fig = px.line(df, x=x_column, y=y_column, title=f"{y_column} over {x_column}")
            st.plotly_chart(fig, use_container_width=True)
            
        elif viz_type == "Scatter Plot":
            x_column = st.selectbox("Select X-axis column", numeric_columns)
            y_column = st.selectbox("Select Y-axis column", numeric_columns, index=min(1, len(numeric_columns)-1))
            
            color_column = st.selectbox("Select color column (optional)", ["None"] + categorical_columns)
            color = None if color_column == "None" else color_column
            
            fig = px.scatter(df, x=x_column, y=y_column, color=color, title=f"{y_column} vs {x_column}")
            st.plotly_chart(fig, use_container_width=True)
            
        elif viz_type == "Pie Chart":
            value_column = st.selectbox("Select value column", numeric_columns)
            name_column = st.selectbox("Select name column", categorical_columns)
            
            fig = px.pie(df, values=value_column, names=name_column, title=f"{value_column} by {name_column}")
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Error visualizing results: {str(e)}")


def main():
    """Main application entry point."""
    try:
        # Initialize connections
        initialize_connections()
        
        # Display header
        display_header()
        
        # Create tabs
        tab1, tab2, tab3 = st.tabs(["Chat", "Query History", "Visualization"])
        
        with tab1:
            display_chat_interface()
            
        with tab2:
            display_cypher_history()
            
        with tab3:
            display_visualization()
            
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        
    finally:
        # Close Neo4j connection when app is done
        if hasattr(st.session_state, "neo4j_connection") and st.session_state.neo4j_connection:
            st.session_state.neo4j_connection.close()


if __name__ == "__main__":
    main()

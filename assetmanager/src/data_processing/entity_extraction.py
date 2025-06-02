"""
Entity extraction module for processing SEC EDGAR Form-13 data.
This replaces the functionality from the '1-parsing-data' notebook.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from tqdm import tqdm

from src.utils.vertex_ai import extract_entities_from_text

logger = logging.getLogger(__name__)

# Prompt templates for entity extraction
MGR_INFO_TEMPLATE = """From the text below, extract the following as json. Do not miss any of these information.
* The tags mentioned below may or may not namespaced. So extract accordingly. Eg: <ns1:tag> is equal to <tag>
* "managerName" - The name from the <n> tag under <filingManager> tag
* "street1" - The manager's street1 address from the <com:street1> tag under <address> tag
* "street2" - The manager's street2 address from the <com:street2> tag under <address> tag
* "city" - The manager's city address from the <com:city> tag under <address> tag
* "stateOrCounty" - The manager's stateOrCounty address from the <com:stateOrCountry> tag under <address> tag
* "zipCode" - The manager's zipCode from the <com:zipCode> tag under <address> tag
* "reportCalendarOrQuarter" - The reportCalendarOrQuarter from the <reportCalendarOrQuarter> tag under <address> tag
* Just return me the JSON enclosed by 3 backticks. No other text in the response

Text:
$ctext
"""

FILING_INFO_TEMPLATE = """The text below contains a list of investments. Each instance of <infoTable> tag represents a unique investment. 
For each investment, please extract the below variables into json then combine into a list enclosed by 3 backticks. Please use the quoted names below while doing this
* "cusip" - The cusip from the <cusip> tag under <infoTable> tag
* "companyName" - The name under the <nameOfIssuer> tag.
* "value" - The value from the <value> tag under <infoTable> tag. Return as a number. 
* "shares" - The sshPrnamt from the <sshPrnamt> tag under <infoTable> tag. Return as a number. 
* "sshPrnamtType" - The sshPrnamtType from the <sshPrnamtType> tag under <infoTable> tag
* "investmentDiscretion" - The investmentDiscretion from the <investmentDiscretion> tag under <infoTable> tag
* "votingSole" - The votingSole from the <votingSole> tag under <infoTable> tag
* "votingShared" - The votingShared from the <votingShared> tag under <infoTable> tag
* "votingNone" - The votingNone from the <votingNone> tag under <infoTable> tag

Output format:
* DO NOT output XML tags in the response. The output should be a valid JSON list enclosed by 3 backticks

Text:
$ctext
"""


def extract_json_from_llm_response(response: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Extract JSON from an LLM response that contains JSON enclosed in backticks.
    
    Args:
        response: LLM response text
        
    Returns:
        Dict or List: The parsed JSON
    """
    # Look for JSON content within triple backticks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # If no backticks, try to find JSON-like content
        json_str = response.strip()
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        logger.error(f"Response: {response}")
        return {}


def split_filing_info(s: str, chunk_size: int = 5) -> List[str]:
    """
    Split filing information to avoid hitting LLM token limits.
    
    Args:
        s: The filing information text to split
        chunk_size: Number of infoTable entries per chunk
        
    Returns:
        List[str]: The chunks of filing information
    """
    pattern = '(</(\\w+:)?infoTable>)'
    splitter_matches = re.findall(pattern, s)
    
    if not splitter_matches:
        return [s]
        
    splitter = splitter_matches[0][0]
    _parts = s.split(splitter)
    
    if len(_parts) > chunk_size:
        chunks_of_list = np.array_split(_parts, len(_parts) / chunk_size)
        chunks = [splitter.join(chunk) + (splitter if i < len(chunks_of_list) - 1 else '') 
                  for i, chunk in enumerate(chunks_of_list)]
    else:
        chunks = [s]
        
    return chunks


def extract_manager_info(xml_content: str) -> Dict[str, Any]:
    """
    Extract manager information from Form-13 XML content.
    
    Args:
        xml_content: The XML content to process
        
    Returns:
        Dict[str, Any]: The extracted manager information
    """
    response = extract_entities_from_text(
        text=xml_content,
        extraction_prompt=MGR_INFO_TEMPLATE,
        temperature=0.0,  # Use deterministic extraction for structured data
    )
    
    return extract_json_from_llm_response(response)


def extract_filing_info(xml_content: str) -> List[Dict[str, Any]]:
    """
    Extract filing information from Form-13 XML content.
    
    Args:
        xml_content: The XML content to process
        
    Returns:
        List[Dict[str, Any]]: The extracted filing information
    """
    chunks = split_filing_info(xml_content)
    all_investments = []
    
    for chunk in chunks:
        response = extract_entities_from_text(
            text=chunk,
            extraction_prompt=FILING_INFO_TEMPLATE,
            temperature=0.0,
            max_output_tokens=2048,
        )
        
        investments = extract_json_from_llm_response(response)
        if isinstance(investments, list):
            all_investments.extend(investments)
        elif investments:  # Handle case where single investment is returned as a dict
            all_investments.append(investments)
    
    return all_investments


def process_form13_file(file_path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Process a Form-13 file to extract all relevant information.
    
    Args:
        file_path: Path to the Form-13 XML file
        
    Returns:
        Tuple[Dict[str, Any], List[Dict[str, Any]]]: Manager info and filing info
    """
    logger.info(f"Processing file: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract manager information
    manager_info = extract_manager_info(content)
    
    # Extract filing information
    filing_info = extract_filing_info(content)
    
    logger.info(f"Extracted information for manager: {manager_info.get('managerName', 'Unknown')}")
    logger.info(f"Extracted {len(filing_info)} investments")
    
    return manager_info, filing_info


def process_form13_directory(directory_path: str) -> List[Dict[str, Any]]:
    """
    Process all Form-13 files in a directory.
    
    Args:
        directory_path: Path to directory containing Form-13 XML files
        
    Returns:
        List[Dict[str, Any]]: Processed data for Neo4j import
    """
    import os
    
    result_data = []
    
    # Find all XML files in the directory
    files = [f for f in os.listdir(directory_path) if f.endswith('.xml')]
    
    for file_name in tqdm(files, desc="Processing Form-13 files"):
        file_path = os.path.join(directory_path, file_name)
        
        try:
            manager_info, filing_info = process_form13_file(file_path)
            
            # Structure data for Neo4j import
            manager_node = {
                "label": "Manager",
                "name": manager_info.get("managerName"),
                "street1": manager_info.get("street1"),
                "street2": manager_info.get("street2"),
                "city": manager_info.get("city"),
                "stateOrCounty": manager_info.get("stateOrCounty"),
                "zipCode": manager_info.get("zipCode"),
                "reportCalendarOrQuarter": manager_info.get("reportCalendarOrQuarter"),
                "file": file_name,
            }
            
            # Add manager node
            result_data.append({
                "type": "node",
                "data": manager_node
            })
            
            # Process filing information
            for investment in filing_info:
                company_node = {
                    "label": "Company",
                    "name": investment.get("companyName"),
                    "cusip": investment.get("cusip"),
                }
                
                # Add company node
                result_data.append({
                    "type": "node",
                    "data": company_node
                })
                
                # Add investment relationship
                investment_rel = {
                    "type": "INVESTED_IN",
                    "from_label": "Manager",
                    "from_key": manager_info.get("managerName"),
                    "to_label": "Company",
                    "to_key": investment.get("companyName"),
                    "value": investment.get("value"),
                    "shares": investment.get("shares"),
                    "sshPrnamtType": investment.get("sshPrnamtType"),
                    "investmentDiscretion": investment.get("investmentDiscretion"),
                    "votingSole": investment.get("votingSole"),
                    "votingShared": investment.get("votingShared"),
                    "votingNone": investment.get("votingNone"),
                }
                
                result_data.append({
                    "type": "relationship",
                    "data": investment_rel
                })
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
    
    return result_data

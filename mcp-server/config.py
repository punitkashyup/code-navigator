"""
Configuration settings for the RAG MCP server.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========================================
# OPENSEARCH CONFIGURATION
# ========================================
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_ADMIN_PW = os.getenv("OPENSEARCH_ADMIN_PW", "MyS3cur3P@ss!")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "code_chunks")
OPENSEARCH_TEXT_FIELD = os.getenv("OPENSEARCH_TEXT_FIELD", "text")
OPENSEARCH_VECTOR_FIELD = os.getenv("OPENSEARCH_VECTOR_FIELD", "vector_field")
OPENSEARCH_TIMEOUT = int(os.getenv("OPENSEARCH_TIMEOUT", "60"))

# ========================================
# EMBEDDING MODEL CONFIGURATION
# ========================================
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "bedrock")  # "bedrock" or "openai"

# Bedrock Settings (Primary)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") 
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_EMBEDDING_MODEL = os.getenv("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
BEDROCK_MAX_POOL_CONNECTIONS = int(os.getenv("BEDROCK_MAX_POOL_CONNECTIONS", "50"))

# OpenAI Settings (Fallback)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

# ========================================
# LLM CONFIGURATION 
# ========================================
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "bedrock"

# OpenAI LLM Settings
QUERY_EXPANSION_MODEL = os.getenv("QUERY_EXPANSION_MODEL", "gpt-3.5-turbo")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "gpt-4o")

# Bedrock LLM Settings (if using Bedrock for LLM)
BEDROCK_QUERY_EXPANSION_MODEL = os.getenv("BEDROCK_QUERY_EXPANSION_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
BEDROCK_RERANKER_MODEL = os.getenv("BEDROCK_RERANKER_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")

# ========================================
# RAG PIPELINE PARAMETERS
# ========================================
QUERY_EXPANSION_N = int(os.getenv("QUERY_EXPANSION_N", "3"))  # Number of additional queries to generate
RERANK_TOP_M = int(os.getenv("RERANK_TOP_M", "5"))  # Number of chunks to return after reranking
BM25_K = int(os.getenv("BM25_K", "5"))  # Number of results from BM25
VECTOR_SEARCH_K = int(os.getenv("VECTOR_SEARCH_K", "5"))  # Number of results from vector search
MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", "100"))  # Maximum number of chunks to return for metadata operations

# ========================================
# SERVER SETTINGS
# ========================================
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
LOG_LEVEL_UVICORN = os.getenv("LOG_LEVEL_UVICORN", "info")

# ========================================
# METADATA STRUCTURE HINT
# ========================================
METADATA_STRUCTURE = {
    "repo": "Repository name (e.g., 'organization/repo-name')",
    "branch": "Branch name (e.g., 'main', 'develop')", 
    "file_path": "File path within repository (e.g., 'src/app.py')",
    "chunk_id": "Unique identifier for the code chunk",
    "language": "Programming language (e.g., 'python', 'javascript')",
    "start_line": "Starting line number in original file",
    "end_line": "Ending line number in original file"
} 
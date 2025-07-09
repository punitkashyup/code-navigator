# Code Search RAG MCP Server

This package provides a Model Context Protocol (MCP) server with advanced RAG (Retrieval-Augmented Generation) capabilities for code search and metadata operations.

## Features

- **Advanced RAG Pipeline**: Query transformation, hybrid search (BM25 + vectors), and reranking
- **Flexible Embedding Options**: Support for AWS Bedrock (recommended) and OpenAI embeddings
- **Metadata Operations**: Tools for retrieving and counting code chunks by metadata
- **MCP Interface**: Built on the Model Context Protocol for easy integration with LLM agents

## Setup

### Prerequisites

- Python 3.9+
- OpenSearch instance with code chunks indexed
- AWS credentials with Bedrock access (recommended) OR OpenAI API key

### Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables by creating a `.env` file based on the provided `env.example`:

```bash
# Copy the example file
cp env.example .env

# Edit with your values
nano .env  # or use your preferred editor
```

The `.env` file should contain all necessary configuration:

```
# OpenSearch Settings
OPENSEARCH_URL=https://your-opensearch-domain.us-east-1.es.amazonaws.com
OPENSEARCH_USER=admin
OPENSEARCH_ADMIN_PW=your_password
OPENSEARCH_INDEX=code_chunks

# Embedding Provider (recommended: bedrock)
EMBEDDING_PROVIDER=bedrock

# AWS Bedrock Settings (Primary Option)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0

# OpenAI Settings (Fallback Option)
OPENAI_API_KEY=your_openai_api_key

# Other settings can be customized as needed
```

## Running the Server

### Local Development

Start the MCP server:

```bash
python -m mcp_server
```

Or with custom host and port:

```bash
python -m mcp_server --host 0.0.0.0 --port 8080
```

### Docker Deployment

The project includes Docker Compose configuration for easy deployment with environment variables:

1. Make sure your `.env` file is set up in the mcp-server directory with all required variables.

2. Start the services:

```bash
docker-compose up -d
```

This will:
- Load environment variables from the `.env` file
- Start the MCP server on port 8080 (or your configured port)
- Start OpenSearch on ports 9200 and 9600
- Initialize the OpenSearch index with the correct schema

To stop the services:

```bash
docker-compose down
```

To remove all data (including OpenSearch volumes):

```bash
docker-compose down -v
```

## MCP Tools

### 1. RAG Tool

Find the most relevant code snippets that match your query.

```python
result = await rag_tool(query="How to implement authentication in Flask?")
```

### 2. Get Chunks by Metadata

Retrieve code chunks matching specific metadata criteria. You can provide any combination of metadata fields - partial matching is supported.

```python
result = await get_chunks_by_metadata_tool(
    metadata_filters={
        "repo": "my-org/my-repo",
        "language": "python"
    }
)
```

### 3. Count Chunks by Metadata

Count code chunks matching specific metadata criteria. You can provide any combination of metadata fields - partial matching is supported.

```python
result = await count_chunks_by_metadata_tool(
    metadata_filters={
        "repo": "my-org/my-repo",
        "branch": "main"
    }
)
```

### 4. Get Metadata by Filters

Retrieve only metadata for chunks matching specific criteria. You can provide any combination of metadata fields - partial matching is supported.

```python
result = await get_metadata_by_filters_tool(
    metadata_filters={
        "file_path": "src/auth.py"
    }
)
```

## Configuration

All configuration options can be set in the `.env` file or as environment variables:

- **OpenSearch Settings**: Connection details, index and field names
- **Embedding Provider**: Choose between Bedrock (recommended) or OpenAI
- **AWS Bedrock Settings**: Credentials and model configuration for embeddings
- **OpenAI Settings**: API key and model configuration (fallback option)
- **LLM Settings**: Model selection for query expansion and reranking
- **RAG Pipeline Parameters**: Query expansion, reranking, and search result parameters
- **Server Settings**: Host, port, and log level

See `env.example` for all available options, model choices, and their default values.

## Metadata Structure

The following metadata fields are available for filtering:

- `repo`: Repository name (e.g., 'organization/repo-name')
- `branch`: Branch name (e.g., 'main', 'develop')
- `file_path`: File path within repository (e.g., 'src/app.py')
- `chunk_id`: Unique identifier for the code chunk
- `language`: Programming language (e.g., 'python', 'javascript')
- `start_line`: Starting line number in original file
- `end_line`: Ending line number in original file 
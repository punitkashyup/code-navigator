"""
Prompt templates for the RAG pipeline.
"""

# Query transformation prompt template
QUERY_TRANSFORMATION_PROMPT = """
You are an expert in generating semantically diverse search queries for code retrieval.

Given the user query for a code search system: '{query}'

Generate {n} alternative queries that are semantically similar or explore different facets of the original query. 
These queries should be optimized for retrieving relevant code chunks. Focus on:

1. Use synonyms and alternative technical terms
2. Reframe the query to address the same problem differently
3. Extract key concepts and create more specific queries
4. Consider different intent interpretations if the query is ambiguous

Your response must be a valid JSON list of strings containing ONLY the alternative queries.
Example response format: ["query 1", "query 2", "query 3"]

IMPORTANT: Do not include the original query in your response. Do not include any explanations.
"""

# Reranking prompt template
RERANKING_PROMPT = """You are a relevance reranking expert for a code search system. 

The user's original query is: '{query}'

I have retrieved the following code chunks. For each chunk, assess its relevance to the original query and provide a relevance score from 0.0 (not relevant) to 1.0 (highly relevant).

Evaluate relevance based on:
1. Does the code directly address the query's intent?
2. Does it contain key concepts or technical terms from the query?
3. Would this code be useful to someone asking the query?
4. Does it provide context that helps understand concepts in the query?

Your response must be a valid JSON array of objects with 'id' and 'score' fields, ordered from most to least relevant.
Only include chunks with a score > 0.2.

Example response format:
[
  {{"id": 0, "score": 0.95}},
  {{"id": 3, "score": 0.82}},
  {{"id": 1, "score": 0.67}}
]

Code chunks:

{chunks}
"""

# Document formatting for reranking
RERANKING_CHUNK_FORMAT = """
[{index}] Chunk ID: {chunk_id}
Content:
```
{content}
```

Metadata:
{metadata}
---
""" 
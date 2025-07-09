import os
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from openai import OpenAI, AsyncOpenAI
import json

# --- Shared Models ---

class ChunkDescription(BaseModel):
    chunk_index: int = Field(description="The 0-based index of the chunk in the original list.")
    relational_description: str = Field(description="A single-line description of what this specific code chunk does or represents.")

class FileChunkDescriptions(BaseModel):
    file_description: str = Field(description="A single-line description of the overall purpose of the file.")
    chunk_descriptions: List[ChunkDescription] = Field(description="A list containing descriptions for each chunk in the file.")

# --- Main Function ---

def generate_descriptions_for_chunks(chunks: List[Dict[str, Any]], full_file_content: str) -> List[Dict[str, Any]]:
    provider = os.getenv("CHUNK_DESC_PROVIDER", "gemini").lower()

    if provider == "gemini":
        return _generate_with_gemini(chunks, full_file_content)
    elif provider == "openai":
        return _generate_with_openai(chunks, full_file_content)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

# --- Async Main Function ---

async def generate_descriptions_for_chunks_async(chunks: List[Dict[str, Any]], full_file_content: str) -> List[Dict[str, Any]]:
    provider = os.getenv("CHUNK_DESC_PROVIDER", "gemini").lower()

    if provider == "gemini":
        return await _generate_with_gemini_async(chunks, full_file_content)
    elif provider == "openai":
        return await _generate_with_openai_async(chunks, full_file_content)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

# --- Gemini Implementation ---

def _generate_with_gemini(chunks: List[Dict[str, Any]], full_file_content: str) -> List[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set. Skipping description generation.")
        return _add_placeholder_descriptions(chunks, reason="API key missing")

    client = genai.Client(api_key=api_key)

    prompt_parts = [
        "Analyze the following source code file and its chunks.",
        "\n--- Full File Content ---\n",
        full_file_content,
        "\n\n--- Code Chunks ---"
    ]

    for i, chunk in enumerate(chunks):
        prompt_parts.append(f"\n\n--- Chunk {i} ---\n{chunk.get('content', '')}")

    prompt_parts += [
        "\n\n--- Instructions ---",
        "Provide a single-line description for the file ('file_description').",
        "For each chunk, provide a single-line description ('relational_description').",
        "Return the result as a JSON object matching the FileChunkDescriptions schema."
    ]

    prompt = "\n".join(prompt_parts)

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': FileChunkDescriptions,
            },
        )

        if response.parsed:
            return _update_chunks_with_descriptions(chunks, response.parsed)
        else:
            print(f"Warning: Gemini response not parsed. Raw text: {response.text}")
            return _add_placeholder_descriptions(chunks, reason="Gemini response parsing failed.")
    except Exception as e:
        print(f"Gemini API error: {e}")
        return _add_placeholder_descriptions(chunks, reason=str(e))

# --- Async Gemini Implementation ---

async def _generate_with_gemini_async(chunks: List[Dict[str, Any]], full_file_content: str) -> List[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set. Skipping description generation.")
        return _add_placeholder_descriptions(chunks, reason="API key missing")

    client = genai.Client(api_key=api_key)

    prompt_parts = [
        "Analyze the following source code file and its chunks.",
        "\n--- Full File Content ---\n",
        full_file_content,
        "\n\n--- Code Chunks ---"
    ]

    for i, chunk in enumerate(chunks):
        prompt_parts.append(f"\n\n--- Chunk {i} ---\n{chunk.get('content', '')}")

    prompt_parts += [
        "\n\n--- Instructions ---",
        "Provide a single-line description for the file ('file_description').",
        "For each chunk, provide a single-line description ('relational_description').",
        "Return the result as a JSON object matching the FileChunkDescriptions schema."
    ]

    prompt = "\n".join(prompt_parts)

    try:
        # Using sync method in an async context since Gemini's Python client doesn't have native async support
        # But by running in an async function, multiple files can be processed concurrently
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-2.0-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': FileChunkDescriptions,
            }
        )

        if response.parsed:
            return _update_chunks_with_descriptions(chunks, response.parsed)
        else:
            print(f"Warning: Gemini response not parsed. Raw text: {response.text}")
            return _add_placeholder_descriptions(chunks, reason="Gemini response parsing failed.")
    except Exception as e:
        print(f"Gemini API error: {e}")
        return _add_placeholder_descriptions(chunks, reason=str(e))

# --- OpenAI Implementation ---

def _generate_with_openai(chunks: List[Dict[str, Any]], full_file_content: str) -> List[Dict[str, Any]]:
    try:
        client = OpenAI()  # Assumes OPENAI_API_KEY is set

        prompt_parts = [
            "Analyze the source code and its chunks.",
            "\n--- Full File Content ---\n",
            full_file_content,
            "\n\n--- Code Chunks ---"
        ]

        for i, chunk in enumerate(chunks):
            prompt_parts.append(f"\n\n--- Chunk {i} ---\n{chunk.get('content', '')}")

        prompt_parts += [
            "\n\n--- Instructions ---",
            "Provide a single-line description for the file ('file_description').",
            "For each chunk, provide a single-line description ('relational_description').",
            "Return the result as a JSON object matching this schema:",
            FileChunkDescriptions.schema_json(indent=2)
        ]

        prompt = "\n".join(prompt_parts)

        # Use structured output parsing
        response = client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured descriptions from code."},
                {"role": "user", "content": prompt}
            ],
            response_format=FileChunkDescriptions
        )

        parsed: FileChunkDescriptions = response.choices[0].message.parsed
        return _update_chunks_with_descriptions(chunks, parsed)

    except Exception as e:
        print(f"OpenAI API error: {e}")
        return _add_placeholder_descriptions(chunks, reason=str(e))

# --- Async OpenAI Implementation ---

async def _generate_with_openai_async(chunks: List[Dict[str, Any]], full_file_content: str) -> List[Dict[str, Any]]:
    try:
        client = AsyncOpenAI()  # Assumes OPENAI_API_KEY is set

        prompt_parts = [
            "Analyze the source code and its chunks.",
            "\n--- Full File Content ---\n",
            full_file_content,
            "\n\n--- Code Chunks ---"
        ]

        for i, chunk in enumerate(chunks):
            prompt_parts.append(f"\n\n--- Chunk {i} ---\n{chunk.get('content', '')}")

        prompt_parts += [
            "\n\n--- Instructions ---",
            "Provide a single-line description for the file ('file_description').",
            "For each chunk, provide a single-line description ('relational_description').",
            "Return the result as a JSON object matching this schema:",
            FileChunkDescriptions.schema_json(indent=2)
        ]

        prompt = "\n".join(prompt_parts)

        # Use structured output parsing with async client
        response = await client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured descriptions from code."},
                {"role": "user", "content": prompt}
            ],
            response_format=FileChunkDescriptions
        )

        parsed: FileChunkDescriptions = response.choices[0].message.parsed
        return _update_chunks_with_descriptions(chunks, parsed)

    except Exception as e:
        print(f"OpenAI API error: {e}")
        return _add_placeholder_descriptions(chunks, reason=str(e))

# --- Helpers ---

def _update_chunks_with_descriptions(chunks: List[Dict[str, Any]], parsed: FileChunkDescriptions) -> List[Dict[str, Any]]:
    file_desc = parsed.file_description
    desc_map = {cd.chunk_index: cd.relational_description for cd in parsed.chunk_descriptions}

    for i, chunk in enumerate(chunks):
        if 'metadata' not in chunk:
            chunk['metadata'] = {}
        chunk['metadata']['file_description'] = file_desc
        chunk['metadata']['relational_description'] = desc_map.get(i, "Description not found.")
    return chunks

def _add_placeholder_descriptions(chunks: List[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
    for chunk in chunks:
        if 'metadata' not in chunk:
            chunk['metadata'] = {}
        chunk['metadata']['file_description'] = f"File description unavailable ({reason})"
        chunk['metadata']['relational_description'] = f"Chunk description unavailable ({reason})"
    return chunks

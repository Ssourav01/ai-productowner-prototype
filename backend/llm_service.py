
import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"


def generate_response(prompt: str) -> str:
    """
    Send a prompt to the local Ollama model
    and return its generated response.
    """

    if not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=600
    )

    response.raise_for_status()

    result = response.json()

    return result["response"].strip()

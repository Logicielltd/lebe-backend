import os
from huggingface_hub import InferenceClient

from typing import Any, Optional
from smolagents.tools import Tool

class AssistantConversation(Tool):
    client = InferenceClient(model="meta-llama/Llama-4-Scout-17B-16E-Instruct")

    output = client.chat.completions.create(
        messages=[
            {"role": "user", "content": "The capital of France is"},
        ],
        stream=False,
        max_tokens=1024,
    )
    print(output.choices[0].message.content)
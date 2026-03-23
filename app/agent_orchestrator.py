"""Generic multi-agent pipeline orchestrator.

Each *agent* is defined by a system prompt and a Pydantic output model.
The orchestrator runs them sequentially, feeding each agent's structured
output into the next agent's context.
"""

import json
import time
from typing import Type

from pydantic import BaseModel

from app.helpers import client as openai_client
from app.logger import setup_logger

logger = setup_logger(__name__)


class AgentStep:
    """Describes a single agent in a pipeline."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        output_model: Type[BaseModel],
        model: str = "gpt-4o-mini",
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.output_model = output_model
        self.model = model


def run_pipeline(
    steps: list[AgentStep],
    initial_input: str,
    extra_context: str = "",
) -> list[dict]:
    """Execute a sequence of agents, passing each output to the next.

    Returns a list of dicts: [{agent_name, output, duration_ms}, ...]
    """
    results: list[dict] = []
    accumulated_context = initial_input
    if extra_context:
        accumulated_context += f"\n\n{extra_context}"

    for step in steps:
        t0 = time.time()

        previous_outputs = ""
        for r in results:
            previous_outputs += f"\n\n--- {r['agent_name']} output ---\n{json.dumps(r['output'], indent=2)}"

        user_content = f"Input:\n{accumulated_context}"
        if previous_outputs:
            user_content += f"\n\nPrevious agent outputs:{previous_outputs}"

        try:
            completion = openai_client.chat.completions.create(
                model=step.model,
                messages=[
                    {"role": "system", "content": step.system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content
            parsed = step.output_model.model_validate_json(raw)
            output = parsed.model_dump()
        except Exception as e:
            logger.error(f"Agent '{step.name}' failed: {e}", exc_info=True)
            output = {"error": str(e)}

        duration_ms = int((time.time() - t0) * 1000)
        results.append({
            "agent_name": step.name,
            "output": output,
            "duration_ms": duration_ms,
        })
        logger.info(f"Agent '{step.name}' completed in {duration_ms}ms")

    return results

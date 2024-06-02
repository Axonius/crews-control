# https://github.com/langchain-ai/langchain/commit/4c087e2bf77c520f300a5cec5424660ad740f41f
"""Tool for asking human input."""

from typing import Callable
from pydantic import Field
from langchain.tools.base import BaseTool


def _print_func(text: str) -> None:
    print("\n")
    print(text)

def input_func() -> str:
    print("Insert your text. Press Ctrl-D (or Ctrl-Z on Windows) to end.")
    contents = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        contents.append(line)
    return "\n".join(contents)

class HumanTool(BaseTool):
    """Tool that adds the capability to ask user for multi line input."""

    name = "HumanTool"
    description = (
        "You can ask a human for guidance when you think you"
        " got stuck or you are not sure what to do next."
        " The input should be a question for the human."
        " This tool version is suitable when you need answers that span over"
        " several lines."
    )
    prompt_func: Callable[[str], None] = _print_func
    input_func: Callable[[], str] = input_func

    def _run(self, query: str) -> str:
        """Use the Multi Line Human input tool."""
        self.prompt_func(query)
        return self.input_func()

    async def _arun(self, query: str) -> str:
        """Use the Multi Line Human tool asynchronously."""
        raise NotImplementedError("Human tool does not support async")

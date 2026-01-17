from typing import Any, List, Optional

from strands import Agent
from strands.agent import SlidingWindowConversationManager
from strands.hooks import HookProvider

from modules.ai.bedrock_model import create_bedrock_model
from settings import Models


def create_agent(
    system_prompt: str,
    model: str = Models.CLAUDE_45,
    tools: Optional[List[Any]] = None,
    hooks: Optional[List[HookProvider]] = None,
    temperature: float = 0.3,
    read_timeout: int = 300,
    connect_timeout: int = 60,
    max_attempts: int = 10,
    maximum_messages_to_keep: int = 30,
    should_truncate_results: bool = True,
    callback_handler: Any = None,
) -> Agent:
    """
    Create configured Strands Agent for invoice extraction

    Args:
        system_prompt: Agent system instructions
        model: Bedrock model ID
        tools: List of tool functions
        hooks: List of HookProvider instances
        temperature: Model temperature
        read_timeout: Model read timeout
        connect_timeout: Model connection timeout
        max_attempts: Retry attempts
        maximum_messages_to_keep: Conversation window size
        should_truncate_results: Truncate long results
        callback_handler: Optional callback handler

    Returns:
        Configured Agent instance
    """
    tools = tools or []
    hooks = hooks or []

    bedrock_model = create_bedrock_model(
        model=model,
        temperature=temperature,
        read_timeout=read_timeout,
        connect_timeout=connect_timeout,
        max_attempts=max_attempts,
    )

    return Agent(
        system_prompt=system_prompt,
        model=bedrock_model,
        conversation_manager=SlidingWindowConversationManager(
            window_size=maximum_messages_to_keep,
            should_truncate_results=should_truncate_results,
        ),
        tools=tools,
        hooks=hooks,
        callback_handler=callback_handler,
    )

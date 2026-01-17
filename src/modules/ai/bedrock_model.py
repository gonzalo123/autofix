from botocore.config import Config
from strands.models import BedrockModel

from settings import Models


def create_bedrock_model(
    model: str = Models.CLAUDE_45,
    temperature: float = 0.3,
    read_timeout: int = 300,
    connect_timeout: int = 60,
    max_attempts: int = 10,
) -> BedrockModel:
    """
    Create configured AWS Bedrock model instance

    Args:
        model: Bedrock model ID from Models enum
        temperature: Model temperature (0.0-1.0)
        read_timeout: Timeout for reading responses (seconds)
        connect_timeout: Timeout for establishing connection (seconds)
        max_attempts: Maximum retry attempts

    Returns:
        Configured BedrockModel instance
    """
    return BedrockModel(
        model_id=model,
        temperature=temperature,
        boto_client_config=Config(
            read_timeout=read_timeout,
            connect_timeout=connect_timeout,
            retries={"max_attempts": max_attempts},
        ),
    )

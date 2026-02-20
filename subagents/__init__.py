"""Sub-agents module — spawn and manage child agents for parallel task delegation."""

from .manager import SubAgentManager, SubAgentRecord
from .meta_tool import MANAGE_SUBAGENTS_DEFINITION, create_subagent_handler

__all__ = [
    "SubAgentManager",
    "SubAgentRecord",
    "MANAGE_SUBAGENTS_DEFINITION",
    "create_subagent_handler",
]

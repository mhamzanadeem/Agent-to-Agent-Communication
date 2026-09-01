from typing import Any, Dict, Optional

from .a2a_protocol import (
    AgentContext,
    ConversationMessage,
    ContextMetadata,
)


class ContextManager:
    """
    Responsible for creating and extending shared A2A context.

    Context contains:
        - conversation history
        - shared state
        - metadata
    """

    @staticmethod
    def create(
        priority: str = "normal",
        deadline: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AgentContext:

        return AgentContext(
            conversation_history=[],
            shared_state={},
            metadata=ContextMetadata(
                priority=priority,
                deadline=deadline,
                source=source,
            ),
        )

    @staticmethod
    def add_message(
        context: AgentContext,
        role: str,
        content: Any,
        agent_id: Optional[str] = None,
    ) -> AgentContext:

        context.conversation_history.append(
            ConversationMessage(
                role=role,
                agent_id=agent_id,
                content=content,
            )
        )

        return context

    @staticmethod
    def update_state(
        context: AgentContext,
        key: str,
        value: Any,
    ) -> AgentContext:

        context.shared_state[key] = value

        return context

    @staticmethod
    def merge_state(
        context: AgentContext,
        state: Dict[str, Any],
    ) -> AgentContext:

        context.shared_state.update(state)

        return context

    @staticmethod
    def child_context(
        context: AgentContext,
        agent_id: str,
        task_description: str,
    ) -> AgentContext:

        child = context.model_copy(deep=True)

        ContextManager.add_message(
            child,
            role="delegation",
            agent_id=agent_id,
            content=task_description,
        )

        return child
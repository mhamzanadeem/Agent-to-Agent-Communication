from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentCapability(BaseModel):
    name: str
    description: str
    input_types: List[str] = Field(default_factory=list)
    output_types: List[str] = Field(default_factory=list)


class AgentCard(BaseModel):
    agent_id: str
    name: str
    description: str
    endpoint: str
    capabilities: List[AgentCapability]
    version: str = "1.0.0"
    active: bool = True


class ConversationMessage(BaseModel):
    role: str
    agent_id: Optional[str] = None
    content: Any
    timestamp: datetime = Field(default_factory=utc_now)


class ContextMetadata(BaseModel):
    priority: str = "normal"
    deadline: Optional[str] = None
    source: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class AgentContext(BaseModel):
    conversation_history: List[ConversationMessage] = Field(
        default_factory=list
    )

    shared_state: Dict[str, Any] = Field(
        default_factory=dict
    )

    metadata: ContextMetadata = Field(
        default_factory=ContextMetadata
    )


class A2AMessage(BaseModel):
    """
    Standard message envelope exchanged between agents.
    """

    task_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )

    parent_task: Optional[str] = None

    agent_id: str

    target_agent_id: Optional[str] = None

    context: AgentContext

    payload: Dict[str, Any] = Field(
        default_factory=dict
    )

    message_type: str = "task"

    created_at: datetime = Field(
        default_factory=utc_now
    )


class TaskEvent(BaseModel):
    task_id: str
    status: TaskStatus
    agent_id: str
    message: str
    data: Dict[str, Any] = Field(
        default_factory=dict
    )
    timestamp: datetime = Field(
        default_factory=utc_now
    )


class TaskRecord(BaseModel):
    task_id: str
    parent_task: Optional[str] = None
    agent_id: str
    status: TaskStatus = TaskStatus.SUBMITTED
    request: Optional[A2AMessage] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    events: List[TaskEvent] = Field(
        default_factory=list
    )
    created_at: datetime = Field(
        default_factory=utc_now
    )
    updated_at: datetime = Field(
        default_factory=utc_now
    )


class AgentRegistry:
    """
    In-memory A2A agent discovery registry.

    Production deployments can replace this with Redis,
    PostgreSQL, Supabase, etc.
    """

    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._lock = asyncio.Lock()

    async def register(self, card: AgentCard) -> AgentCard:
        async with self._lock:
            self._agents[card.agent_id] = card

        return card

    async def unregister(self, agent_id: str) -> None:
        async with self._lock:
            self._agents.pop(agent_id, None)

    async def get(self, agent_id: str) -> Optional[AgentCard]:
        async with self._lock:
            return self._agents.get(agent_id)

    async def list_agents(self) -> List[AgentCard]:
        async with self._lock:
            return list(self._agents.values())

    async def find_by_capability(
        self,
        capability: str,
    ) -> List[AgentCard]:

        async with self._lock:
            agents = list(self._agents.values())

        matches = []

        for agent in agents:
            for capability_item in agent.capabilities:
                if capability.lower() in capability_item.name.lower():
                    matches.append(agent)
                    break

        return matches


class TaskStore:
    """
    Asynchronous task/state store.

    This provides:
    - task state
    - status updates
    - results
    - errors
    - event history
    """

    def __init__(self):
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        message: A2AMessage,
    ) -> TaskRecord:

        record = TaskRecord(
            task_id=message.task_id,
            parent_task=message.parent_task,
            agent_id=message.agent_id,
            request=message,
        )

        async with self._lock:
            self._tasks[message.task_id] = record

        return record

    async def get(
        self,
        task_id: str,
    ) -> Optional[TaskRecord]:

        async with self._lock:
            return self._tasks.get(task_id)

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        agent_id: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Optional[TaskRecord]:

        async with self._lock:

            task = self._tasks.get(task_id)

            if not task:
                return None

            task.status = status
            task.updated_at = utc_now()

            event = TaskEvent(
                task_id=task_id,
                status=status,
                agent_id=agent_id,
                message=message,
                data=data or {},
            )

            task.events.append(event)

            return task

    async def complete(
        self,
        task_id: str,
        agent_id: str,
        result: Dict[str, Any],
    ) -> Optional[TaskRecord]:

        async with self._lock:

            task = self._tasks.get(task_id)

            if not task:
                return None

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.updated_at = utc_now()

            task.events.append(
                TaskEvent(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    agent_id=agent_id,
                    message="Task completed",
                    data=result,
                )
            )

            return task

    async def fail(
        self,
        task_id: str,
        agent_id: str,
        error: str,
    ) -> Optional[TaskRecord]:

        async with self._lock:

            task = self._tasks.get(task_id)

            if not task:
                return None

            task.status = TaskStatus.FAILED
            task.error = error
            task.updated_at = utc_now()

            task.events.append(
                TaskEvent(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    agent_id=agent_id,
                    message=error,
                )
            )

            return task
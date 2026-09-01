from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import httpx

from .a2a_protocol import (
    A2AMessage,
    AgentContext,
    AgentRegistry,
    TaskStatus,
    TaskStore,
)
from .context_manager import ContextManager
from .config import settings


class OrchestratorAgent:

    def __init__(
        self,
        registry: AgentRegistry,
        task_store: TaskStore,
    ):

        self.registry = registry
        self.task_store = task_store

        self.agent_id = "orchestrator-1"

    async def discover_workers(self):

        agents = await self.registry.list_agents()

        return [
            agent
            for agent in agents
            if agent.agent_id != self.agent_id
        ]

    async def delegate(
        self,
        parent_message: A2AMessage,
        worker_id: str,
        payload: Dict[str, Any],
    ) -> str:

        worker = await self.registry.get(worker_id)

        if not worker:
            raise ValueError(
                f"Worker {worker_id} is not registered"
            )

        child_context = ContextManager.child_context(
            parent_message.context,
            worker_id,
            payload.get("instruction", ""),
        )

        child_message = A2AMessage(
            parent_task=parent_message.task_id,
            agent_id=self.agent_id,
            target_agent_id=worker_id,
            context=child_context,
            payload=payload,
        )

        await self.task_store.create(
            child_message
        )

        # In a distributed deployment this URL can point
        # to another agent service.
        url = (
            settings.A2A_BASE_URL
            + f"/a2a/agents/{worker_id}/tasks"
        )

        async with httpx.AsyncClient(
            timeout=120
        ) as client:

            response = await client.post(
                url,
                json=child_message.model_dump(
                    mode="json"
                ),
            )

            response.raise_for_status()

        return child_message.task_id

    async def wait_for_task(
        self,
        task_id: str,
        timeout: int = 120,
    ):

        start = asyncio.get_event_loop().time()

        while True:

            task = await self.task_store.get(
                task_id
            )

            if not task:
                raise RuntimeError(
                    f"Task {task_id} disappeared"
                )

            if task.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            ):
                return task

            elapsed = (
                asyncio.get_event_loop().time()
                - start
            )

            if elapsed > timeout:

                raise TimeoutError(
                    f"Task {task_id} timed out"
                )

            await asyncio.sleep(0.5)

    async def execute(
        self,
        message: A2AMessage,
    ) -> Dict[str, Any]:

        await self.task_store.update_status(
            message.task_id,
            TaskStatus.WORKING,
            self.agent_id,
            "Orchestrator analyzing task",
        )

        product = message.payload.get(
            "product",
            "new eco-friendly product",
        )

        workers = await self.discover_workers()

        worker_ids = {
            worker.agent_id
            for worker in workers
        }

        required_workers = [
            "research-1",
            "writer-1",
            "strategist-1",
        ]

        missing = [
            worker
            for worker in required_workers
            if worker not in worker_ids
        ]

        if missing:
            raise RuntimeError(
                f"Missing required workers: {missing}"
            )

        # -------------------------------------------------
        # STEP 1: Research
        # -------------------------------------------------

        research_task_id = await self.delegate(
            message,
            "research-1",
            {
                "instruction": (
                    "Research the market and competitors "
                    "for the requested eco-friendly product."
                ),
                "product": product,
            },
        )

        research_task = await self.wait_for_task(
            research_task_id
        )

        if research_task.status == TaskStatus.FAILED:
            raise RuntimeError(
                research_task.error
                or "Research task failed"
            )

        research = research_task.result

        ContextManager.merge_state(
            message.context,
            {
                "research": research,
            },
        )

        ContextManager.add_message(
            message.context,
            role="agent_result",
            agent_id="research-1",
            content=research,
        )

        # -------------------------------------------------
        # STEP 2: Writer
        # -------------------------------------------------

        writer_task_id = await self.delegate(
            message,
            "writer-1",
            {
                "instruction": (
                    "Create campaign copy using the "
                    "research output."
                ),
                "product": product,
                "research": research,
            },
        )

        writer_task = await self.wait_for_task(
            writer_task_id
        )

        if writer_task.status == TaskStatus.FAILED:
            raise RuntimeError(
                writer_task.error
                or "Writer task failed"
            )

        campaign_copy = writer_task.result

        ContextManager.merge_state(
            message.context,
            {
                "campaign_copy": campaign_copy,
            },
        )

        ContextManager.add_message(
            message.context,
            role="agent_result",
            agent_id="writer-1",
            content=campaign_copy,
        )

        # -------------------------------------------------
        # STEP 3: Strategist
        # -------------------------------------------------

        strategist_task_id = await self.delegate(
            message,
            "strategist-1",
            {
                "instruction": (
                    "Develop a distribution strategy using "
                    "the research and campaign copy."
                ),
                "product": product,
                "research": research,
                "campaign_copy": campaign_copy,
            },
        )

        strategist_task = await self.wait_for_task(
            strategist_task_id
        )

        if strategist_task.status == TaskStatus.FAILED:
            raise RuntimeError(
                strategist_task.error
                or "Strategist task failed"
            )

        strategy = strategist_task.result

        ContextManager.merge_state(
            message.context,
            {
                "strategy": strategy,
            },
        )

        ContextManager.add_message(
            message.context,
            role="agent_result",
            agent_id="strategist-1",
            content=strategy,
        )

        # -------------------------------------------------
        # FINAL RESULT
        # -------------------------------------------------

        final_result = {
            "campaign": {
                "product": product,
                "research": research,
                "campaign_copy": campaign_copy,
                "distribution_strategy": strategy,
            },
            "workflow": {
                "orchestrator": self.agent_id,
                "workers": [
                    "research-1",
                    "writer-1",
                    "strategist-1",
                ],
                "research_task_id": research_task_id,
                "writer_task_id": writer_task_id,
                "strategist_task_id": strategist_task_id,
            },
            "shared_state": message.context.shared_state,
            "conversation_history": [
                item.model_dump(mode="json")
                for item in message.context.conversation_history
            ],
        }

        await self.task_store.complete(
            message.task_id,
            self.agent_id,
            final_result,
        )

        return final_result
from __future__ import annotations

import asyncio
import uuid
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .a2a_protocol import (
    A2AMessage,
    AgentCard,
    AgentRegistry,
    AgentCapability,
    TaskStatus,
    TaskStore,
)
from .context_manager import ContextManager
from .orchestrator import OrchestratorAgent
from .worker_agents import build_workers
from .config import settings


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "A2A multi-agent marketing system with "
        "orchestrator and worker agents."
    ),
)


registry = AgentRegistry()
task_store = TaskStore()
orchestrator = OrchestratorAgent(
    registry,
    task_store,
)

workers = []


@app.on_event("startup")
async def startup():

    global workers

    workers = build_workers(
        task_store
    )

    orchestrator_card = AgentCard(
        agent_id="orchestrator-1",
        name="Orchestrator Agent",
        description=(
            "Coordinates specialized agents and "
            "combines their results."
        ),
        endpoint="/a2a/orchestrate",
        capabilities=[
            AgentCapability(
                name="task_decomposition",
                description=(
                    "Breaks complex marketing tasks "
                    "into worker subtasks."
                ),
                input_types=["marketing_task"],
                output_types=["campaign"],
            )
        ],
    )

    await registry.register(
        orchestrator_card
    )

    for worker in workers:
        await registry.register(
            worker.card()
        )


@app.get("/")
async def root():

    return {
        "name": settings.APP_NAME,
        "status": "running",
        "protocol": "A2A",
        "agents": [
            agent.agent_id
            for agent in await registry.list_agents()
        ],
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "agents": len(
            await registry.list_agents()
        ),
    }


# ---------------------------------------------------------
# A2A DISCOVERY
# ---------------------------------------------------------

@app.post(
    "/a2a/agents/register",
    response_model=AgentCard,
)
async def register_agent(
    card: AgentCard,
):

    return await registry.register(
        card
    )


@app.get(
    "/a2a/agents",
)
async def list_agents():

    agents = await registry.list_agents()

    return {
        "agents": [
            agent.model_dump(mode="json")
            for agent in agents
        ]
    }


@app.get(
    "/a2a/agents/{agent_id}",
)
async def get_agent(
    agent_id: str,
):

    agent = await registry.get(
        agent_id
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Agent not found",
        )

    return agent


@app.get(
    "/a2a/discover/{capability}",
)
async def discover_capability(
    capability: str,
):

    agents = await registry.find_by_capability(
        capability
    )

    return {
        "capability": capability,
        "agents": [
            agent.model_dump(mode="json")
            for agent in agents
        ],
    }


# ---------------------------------------------------------
# ORCHESTRATOR
# ---------------------------------------------------------

@app.post(
    "/a2a/orchestrate",
)
async def orchestrate(
    message: A2AMessage,
):

    if message.agent_id != "orchestrator-1":
        raise HTTPException(
            status_code=400,
            detail=(
                "Messages sent to this endpoint "
                "must originate from orchestrator-1."
            ),
        )

    await task_store.create(
        message
    )

    asyncio.create_task(
        _run_orchestrator(message)
    )

    return JSONResponse(
        status_code=202,
        content={
            "task_id": message.task_id,
            "status": TaskStatus.SUBMITTED.value,
            "message": (
                "Orchestration task accepted."
            ),
            "status_url": (
                f"/a2a/tasks/{message.task_id}"
            ),
        },
    )


async def _run_orchestrator(
    message: A2AMessage,
):

    try:

        await orchestrator.execute(
            message
        )

    except Exception as exc:

        await task_store.fail(
            message.task_id,
            "orchestrator-1",
            str(exc),
        )


# ---------------------------------------------------------
# WORKER TASK ENDPOINTS
# ---------------------------------------------------------

@app.post(
    "/a2a/agents/{agent_id}/tasks",
)
async def submit_worker_task(
    agent_id: str,
    message: A2AMessage,
):

    agent = None

    for worker in workers:

        if worker.agent_id == agent_id:
            agent = worker
            break

    if not agent:

        raise HTTPException(
            status_code=404,
            detail=f"Worker {agent_id} not found",
        )

    if message.target_agent_id != agent_id:

        raise HTTPException(
            status_code=400,
            detail=(
                "target_agent_id does not match "
                "URL agent_id"
            ),
        )

    existing = await task_store.get(
        message.task_id
    )

    if not existing:
        await task_store.create(
            message
        )

    asyncio.create_task(
        agent.run(message)
    )

    return JSONResponse(
        status_code=202,
        content={
            "task_id": message.task_id,
            "agent_id": agent_id,
            "status": TaskStatus.SUBMITTED.value,
            "status_url": (
                f"/a2a/tasks/{message.task_id}"
            ),
        },
    )


# ---------------------------------------------------------
# TASK STATUS
# ---------------------------------------------------------

@app.get(
    "/a2a/tasks/{task_id}",
)
async def get_task(
    task_id: str,
):

    task = await task_store.get(
        task_id
    )

    if not task:

        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task.model_dump(
        mode="json"
    )


@app.get(
    "/a2a/tasks/{task_id}/events",
)
async def get_task_events(
    task_id: str,
):

    task = await task_store.get(
        task_id
    )

    if not task:

        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return {
        "task_id": task_id,
        "events": [
            event.model_dump(
                mode="json"
            )
            for event in task.events
        ],
    }


# ---------------------------------------------------------
# EXAMPLE TASK
# ---------------------------------------------------------

@app.post(
    "/demo/marketing-campaign",
)
async def demo_marketing_campaign():

    task_id = str(
        uuid.uuid4()
    )

    context = ContextManager.create(
        priority="high",
        deadline="2026-12-31",
        source="demo",
    )

    ContextManager.add_message(
        context,
        role="user",
        content=(
            "Create a marketing campaign for "
            "a new eco-friendly product."
        ),
    )

    message = A2AMessage(
        task_id=task_id,
        parent_task=None,
        agent_id="orchestrator-1",
        context=context,
        payload={
            "product": (
                "A reusable, biodegradable "
                "home-cleaning product line."
            )
        },
    )

    await task_store.create(
        message
    )

    asyncio.create_task(
        _run_orchestrator(message)
    )

    return {
        "task_id": task_id,
        "status": "submitted",
        "message": (
            "Marketing campaign workflow started."
        ),
        "status_url": (
            f"/a2a/tasks/{task_id}"
        ),
    }
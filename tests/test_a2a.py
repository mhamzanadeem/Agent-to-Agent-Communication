import pytest

from app.a2a_protocol import (
    A2AMessage,
    AgentContext,
    AgentRegistry,
    AgentCard,
    AgentCapability,
    TaskStore,
)

from app.context_manager import ContextManager


@pytest.mark.asyncio
async def test_agent_registration():

    registry = AgentRegistry()

    card = AgentCard(
        agent_id="test-agent",
        name="Test Agent",
        description="Testing agent",
        endpoint="/test",
        capabilities=[
            AgentCapability(
                name="testing",
                description="Testing",
            )
        ],
    )

    await registry.register(card)

    agent = await registry.get(
        "test-agent"
    )

    assert agent is not None
    assert agent.agent_id == "test-agent"


@pytest.mark.asyncio
async def test_capability_discovery():

    registry = AgentRegistry()

    card = AgentCard(
        agent_id="research-1",
        name="Research Agent",
        description="Research",
        endpoint="/research",
        capabilities=[
            AgentCapability(
                name="market_research",
                description="Market research",
            )
        ],
    )

    await registry.register(card)

    matches = await registry.find_by_capability(
        "market_research"
    )

    assert len(matches) == 1
    assert matches[0].agent_id == "research-1"


def test_context_sharing():

    context = ContextManager.create(
        priority="high"
    )

    ContextManager.add_message(
        context,
        role="user",
        content="Create a campaign",
    )

    ContextManager.update_state(
        context,
        "product",
        "Reusable bottle",
    )

    assert (
        context.shared_state["product"]
        == "Reusable bottle"
    )

    assert len(
        context.conversation_history
    ) == 1


@pytest.mark.asyncio
async def test_task_store():

    store = TaskStore()

    message = A2AMessage(
        agent_id="test-agent",
        context=AgentContext(),
        payload={
            "hello": "world"
        },
    )

    task = await store.create(
        message
    )

    assert task.task_id == message.task_id

    await store.update_status(
        message.task_id,
        "working",
        "test-agent",
        "Started",
    )

    updated = await store.get(
        message.task_id
    )

    assert updated.status == "working"
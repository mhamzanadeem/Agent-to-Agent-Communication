from __future__ import annotations

import asyncio
from typing import Any, Dict

from groq import AsyncGroq

from .a2a_protocol import (
    A2AMessage,
    AgentCard,
    AgentCapability,
    TaskStatus,
)
from .config import settings


class LLMClient:
    """
    Groq client.

    Groq exposes an OpenAI-compatible chat-completions API,
    but the native Groq Python SDK is used here.
    """

    def __init__(self):
        self.client = AsyncGroq(
            api_key=settings.GROQ_API_KEY
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        response = await self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            temperature=0.4,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        )

        return response.choices[0].message.content or ""


class BaseWorkerAgent:

    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        capabilities: list[AgentCapability],
        task_store,
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.task_store = task_store
        self.llm = LLMClient()

    def card(self) -> AgentCard:

        return AgentCard(
            agent_id=self.agent_id,
            name=self.name,
            description=self.description,
            endpoint=f"/a2a/agents/{self.agent_id}/tasks",
            capabilities=self.capabilities,
        )

    async def execute(
        self,
        message: A2AMessage,
    ) -> Dict[str, Any]:

        raise NotImplementedError

    async def run(
        self,
        message: A2AMessage,
    ):

        task_id = message.task_id

        await self.task_store.update_status(
            task_id,
            TaskStatus.WORKING,
            self.agent_id,
            f"{self.name} started processing",
        )

        try:

            result = await self.execute(message)

            await self.task_store.complete(
                task_id,
                self.agent_id,
                result,
            )

        except Exception as exc:

            await self.task_store.fail(
                task_id,
                self.agent_id,
                str(exc),
            )


class ResearchAgent(BaseWorkerAgent):

    def __init__(self, task_store):

        super().__init__(
            agent_id="research-1",
            name="Research Agent",
            description=(
                "Researches eco-friendly markets, competitors, "
                "customer segments and positioning."
            ),
            capabilities=[
                AgentCapability(
                    name="market_research",
                    description=(
                        "Analyze markets, customer segments, "
                        "competitors and positioning."
                    ),
                    input_types=["marketing_task"],
                    output_types=["research_report"],
                )
            ],
            task_store=task_store,
        )

    async def execute(
        self,
        message: A2AMessage,
    ) -> Dict[str, Any]:

        product = message.payload.get(
            "product",
            "eco-friendly product",
        )

        await self.task_store.update_status(
            message.task_id,
            TaskStatus.WORKING,
            self.agent_id,
            "Analyzing market and competitors",
        )

        prompt = f"""
You are the Research Agent in a multi-agent marketing system.

Research the following product:

{product}

Produce a useful strategic research report covering:

1. Target customers
2. Customer pain points
3. Market trends
4. Five likely competitor categories
5. Competitive positioning
6. Differentiation opportunities
7. Marketing risks
8. Recommended positioning statement

Do not invent precise statistics.
If data is unavailable, clearly label assumptions.
Return structured sections.
"""

        result = await self.llm.generate(
            system_prompt=(
                "You are an expert market research analyst."
            ),
            user_prompt=prompt,
        )

        return {
            "agent": self.agent_id,
            "type": "research_report",
            "product": product,
            "report": result,
        }


class WriterAgent(BaseWorkerAgent):

    def __init__(self, task_store):

        super().__init__(
            agent_id="writer-1",
            name="Writer Agent",
            description=(
                "Creates marketing campaign messaging, "
                "copy and creative concepts."
            ),
            capabilities=[
                AgentCapability(
                    name="campaign_writing",
                    description=(
                        "Create marketing copy and campaign assets."
                    ),
                    input_types=[
                        "marketing_task",
                        "research_report",
                    ],
                    output_types=[
                        "campaign_copy",
                    ],
                )
            ],
            task_store=task_store,
        )

    async def execute(
        self,
        message: A2AMessage,
    ) -> Dict[str, Any]:

        product = message.payload.get(
            "product",
            "eco-friendly product",
        )

        research = message.payload.get(
            "research",
            "No research provided.",
        )

        await self.task_store.update_status(
            message.task_id,
            TaskStatus.WORKING,
            self.agent_id,
            "Writing campaign assets",
        )

        prompt = f"""
You are the Writer Agent.

Create a complete marketing campaign for:

PRODUCT:
{product}

MARKET RESEARCH:
{research}

Create:

1. Campaign name
2. Core idea
3. Brand promise
4. Tagline options
5. Landing page headline
6. Landing page subheadline
7. Three social media posts
8. One email campaign
9. Call-to-action options
10. Short-form video concept

Keep the messaging persuasive but avoid unsupported environmental
claims or greenwashing.
"""

        result = await self.llm.generate(
            system_prompt=(
                "You are an expert marketing copywriter "
                "specializing in sustainable brands."
            ),
            user_prompt=prompt,
        )

        return {
            "agent": self.agent_id,
            "type": "campaign_copy",
            "product": product,
            "copy": result,
        }


class StrategistAgent(BaseWorkerAgent):

    def __init__(self, task_store):

        super().__init__(
            agent_id="strategist-1",
            name="Strategist Agent",
            description=(
                "Develops campaign strategy, channel mix, "
                "launch plan and measurement framework."
            ),
            capabilities=[
                AgentCapability(
                    name="distribution_strategy",
                    description=(
                        "Recommend channels, launch sequencing, "
                        "KPIs and campaign strategy."
                    ),
                    input_types=[
                        "marketing_task",
                        "research_report",
                        "campaign_copy",
                    ],
                    output_types=[
                        "distribution_strategy",
                    ],
                )
            ],
            task_store=task_store,
        )

    async def execute(
        self,
        message: A2AMessage,
    ) -> Dict[str, Any]:

        product = message.payload.get(
            "product",
            "eco-friendly product",
        )

        research = message.payload.get(
            "research",
            "",
        )

        campaign_copy = message.payload.get(
            "campaign_copy",
            "",
        )

        await self.task_store.update_status(
            message.task_id,
            TaskStatus.WORKING,
            self.agent_id,
            "Developing distribution strategy",
        )

        prompt = f"""
You are the Strategist Agent.

Develop a launch and distribution strategy for:

PRODUCT:
{product}

RESEARCH:
{research}

CAMPAIGN COPY:
{campaign_copy}

Provide:

1. Recommended customer segments
2. Primary channels
3. Secondary channels
4. Organic strategy
5. Paid strategy
6. Influencer/creator strategy
7. Launch timeline
8. Content cadence
9. KPI framework
10. Testing plan
11. Budget allocation percentages
12. Biggest strategic risks

Prioritize practical recommendations.
"""

        result = await self.llm.generate(
            system_prompt=(
                "You are a senior growth and marketing strategist."
            ),
            user_prompt=prompt,
        )

        return {
            "agent": self.agent_id,
            "type": "distribution_strategy",
            "product": product,
            "strategy": result,
        }


def build_workers(task_store):

    return [
        ResearchAgent(task_store),
        WriterAgent(task_store),
        StrategistAgent(task_store),
    ]
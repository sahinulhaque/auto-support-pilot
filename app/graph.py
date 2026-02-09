# graph.py

import logging
import os
from typing import Dict, cast
import uuid
from dotenv import load_dotenv
from fastapi import WebSocket
from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.runnables import ConfigurableField, RunnableConfig

from app.nodes.generalChatNode import generalChatNode
from app.nodes.humanInLoopNode import humanInLoopNode
from app.nodes.classifyIntentNode import classifyIntentNode
from app.nodes.ragNode import ragNode
from app.nodes.salesNode import salesNode
from app.utility import (
    GraphContext,
    GraphState,
    InterruptState,
    SocketRequest,
    SocketResponse,
)

load_dotenv()
logger = logging.getLogger(__name__)

LLM = ChatOpenAI(
    model=os.getenv("MODEL", "gpt-5-nano"),
    max_completion_tokens=512,
    temperature=0.2,
    reasoning_effort="minimal",  # Minimize token cost.
).configurable_fields(
    max_tokens=ConfigurableField(
        id="output_max_token",
        name="Dynamic max token",
        description="Each graph node can set max output token. Minimize token cost.",
    ),
    reasoning_effort=ConfigurableField(
        id="output_reasoning_effort",
        name="Dynamic reasoning [minimal,low,medium,high]",
        description="Each graph node can decide reasoning. Minimum reasoning minimize token cost.",
    ),
)

ACTIVE_SESSION: Dict[str, str] = {}


def getThreadId(userId: str) -> str:
    global ACTIVE_SESSION
    if userId not in ACTIVE_SESSION:
        ACTIVE_SESSION[userId] = str(uuid.uuid4())
    return ACTIVE_SESSION[userId]


def routeNode(s: GraphState) -> str:
    if s.intent == "Support":
        return "rag"
    if s.intent == "Sales":
        return "humanInLoop"
    return "generalChat"


def getCompiledGraph():
    try:
        graph = StateGraph(state_schema=GraphState, context_schema=GraphContext)

        # Nodes
        graph.add_node("classifyIntent", classifyIntentNode)
        graph.add_node("rag", ragNode)
        graph.add_node("humanInLoop", humanInLoopNode)
        graph.add_node("sales", salesNode)
        graph.add_node("generalChat", generalChatNode)

        graph.set_entry_point("classifyIntent")
        graph.add_conditional_edges(
            "classifyIntent",
            routeNode,
            {"rag": "rag", "humanInLoop": "humanInLoop", "generalChat": "generalChat"},
        )  # humanInLoop-> sales or END;
        graph.add_edge("rag", END)
        graph.add_edge("sales", END)
        graph.add_edge("generalChat", END)

        inMemoryCheckPointer = InMemorySaver()
        compiledGraph = graph.compile(checkpointer=inMemoryCheckPointer)
        return compiledGraph
    except Exception as err:
        logger.exception(
            "Graph level exception. %s", err, extra={"method": "getCompiledGraph"}
        )
        raise


def processRequest(request: SocketRequest, updateStatus: str = "") -> GraphState:
    try:
        return GraphState(
            userId=request.userId,
            requestId=request.requestId or "",
            query=request.message,
            status=updateStatus or "initializing",
            history=None,
            context=None,
            intent=None,
            order=None,
            response=None,
            summary=None,
        )
    except Exception as err:
        logger.exception(
            "Graph level exception. %s", err, extra={"method": "processRequest"}
        )
        raise


async def runGraph(request: SocketRequest, ws: WebSocket):
    try:
        logger.info("Starting Graph...")
        graphInput = processRequest(request)

        config = RunnableConfig(configurable={"thread_id": getThreadId(request.userId)})
        pilotGraph = getCompiledGraph()
        curr_state = await pilotGraph.aget_state(config)

        logger.info(curr_state.next)

        if curr_state.next and request.status == "interrupted":
            """Resume from interrupt"""
            await interruptedGraph(request, ws, config)
        else:
            """Starting a new Lanchain Graph"""
            graphContext = GraphContext(llm=LLM)
            pilotGraph = getCompiledGraph()
            rawResponse = await pilotGraph.ainvoke(
                input=graphInput,
                context=graphContext,
                config=config,
            )
            logger.info("Graph invoked, %s", getThreadId(request.userId))

            if "__interrupt__" in rawResponse:
                """Human in loop"""
                tempObj = rawResponse["__interrupt__"][-1].value
                interruptValue = InterruptState(
                    assistantQuery=tempObj.assistantQuery,
                    requestId=tempObj.requestId,
                    userResponse=tempObj.userResponse,
                )
                if ws:
                    await ws.send_json(
                        {
                            "status": "interrupted",
                            "content": interruptValue.assistantQuery,
                        }
                    )
            else:
                graphResponse = GraphState.model_validate(rawResponse, extra="ignore")
                await ws.send_json(
                    data=SocketResponse(
                        status="chat", content=graphResponse.response or ""
                    ).model_dump()
                )
    except Exception as err:
        logger.exception("Graph level exception. %s", err, extra={"method": "runGraph"})
        raise


async def interruptedGraph(
    request: SocketRequest, ws: WebSocket, config: RunnableConfig
):
    try:

        graphInput = InterruptState(
            requestId=request.requestId or "",
            userResponse=request.message,
            assistantQuery=None,
        )

        command = Command(resume=graphInput)
        logger.info("Interrupting Graph, %s", getThreadId(request.userId))
        # Re-Invoking Graph
        graphContext = GraphContext(llm=cast(ChatOpenAI, LLM))
        pilotGraph = getCompiledGraph()
        aiResponse = await pilotGraph.ainvoke(
            input=command,
            context=graphContext,
            config=config,
        )

        graphResponse = GraphState.model_validate(
            aiResponse,
            extra="ignore",
        )

        await ws.send_json(
            data=SocketResponse(
                status="chat", content=graphResponse.response or ""
            ).model_dump()
        )

    except Exception as err:
        logger.exception(
            "Interrupted Graph level exception. %s",
            err,
            extra={"method": "interruptedGraph"},
        )
        raise

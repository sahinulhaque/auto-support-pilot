# humanInLoopNode.py

import logging
from typing import Literal
from app.utility import GraphContext, GraphState, InterruptState, OrderDetails
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from langgraph.graph import END
from langgraph.errors import GraphInterrupt

logger = logging.getLogger(__name__)


async def humanInLoopNode(state: GraphState, runtime: Runtime[GraphContext]) -> Command[
    Literal[
        "sales",
        END,
    ]
]:
    try:
        payload = InterruptState(
            requestId=state.requestId, assistantQuery=None, userResponse=None
        )

        order = state.order or OrderDetails(orderId=None, orderItem=None)
        # Check Order id and Item exists or not
        if order.orderId and order.orderItem:
            state.status = "human in loop not interrupted"
            logger.info("Node status: %s", state.status)
            return Command(update={"status": state.status}, goto="sales")

        payload.assistantQuery = f"Plase provide {'order id' if not order.orderId else ''}{' and ' if not order.orderId else ''}item."
        state.status = "human in loop interrupted"
        logger.info("Node status: %s", state.status)
        resp = interrupt(value=payload)
        interruptResponse = InterruptState(
            requestId=resp["requestId"],
            userResponse=resp["userResponse"],
            assistantQuery=resp["assistantQuery"],
        )

        if interruptResponse.userResponse:
            llm = runtime.context.llm
            structured_llm = llm.with_structured_output(OrderDetails).with_config(
                configurable={"output_max_token": 500}
            )
            order = await structured_llm.ainvoke(
                f"You are very intelligent AI. Extract values from {interruptResponse.userResponse}"
            )
            state.status = "human in loop resumed, user answered"
            logger.info("Node status: %s", state.status)
            return Command(
                update={
                    "order": order,
                    "status": state.status,
                },
                goto="sales",
            )
        state.status = "human in loop finished, without answering"
        logger.info("Node status: %s", state.status)
        return Command(goto=END)
    except GraphInterrupt as gerr:
        raise
    except Exception as err:
        logger.exception(
            "Node level exception. %s",
            err,
            extra={"requestId": state.requestId, "nodeName": "humanInLoopNode"},
        )
        raise

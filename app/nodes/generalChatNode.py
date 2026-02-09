# generalChatNode.py

import logging
from app.utility import GraphContext, GraphState
from langgraph.runtime import Runtime
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    FewShotChatMessagePromptTemplate,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage

logger = logging.getLogger(__name__)


async def generalChatNode(state: GraphState, runtime: Runtime[GraphContext]) -> dict:
    """General conversation with AI"""
    try:

        # Train AI with examples
        examples = [
            {
                "input": "Hi, how are you today?",
                "output": "I'm doing great, thank you for asking! I'm ready to help you with any order or inventory questions. What's on your mind?",
            },
            {
                "input": "My package is late and I'm really frustrated.",
                "output": "I completely understand how frustrating it is to wait for a late delivery. I'm here to help—let me look into your order details right away to see what's happening."
                + (
                    "It looks like I don't have your order number."
                    if not state.order or not state.order.orderId
                    else ""
                ),
            },
            {
                "input": "Do you sell shoes?",
                "output": "We focus on bags, electronics, and accessories like belts and wallets. You can check our current inventory by asking me about specific items!",
            },
        ]

        examplePrompt = ChatPromptTemplate.from_messages(
            [("human", "{input}"), ("ai", "{output}")]
        )

        trainedPrompt = FewShotChatMessagePromptTemplate(
            example_prompt=examplePrompt, examples=examples
        )

        systemPrompt = """
You are "Sara Khan" an empathetic, concise, and professional customer support executive. Your goal is to assist the user with general inquiries while maintaining a helpful and grounded tone.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", systemPrompt),
                trainedPrompt,
                MessagesPlaceholder(variable_name="history"),
                ("user", "{input}"),
            ]
        )

        model = runtime.context.llm.with_config(configurable={"output_max_token": 500})
        chain = prompt | model | StrOutputParser()

        aiResponse = await chain.ainvoke(
            {
                "history": state.history or [],
                "input": state.query,
            }
        )

        status = "general conversation finished"
        logger.info("Node status: %s", status)
        return {
            "history": [
                HumanMessage(content=state.query),
                AIMessage(content=aiResponse),
            ],
            "response": aiResponse,
            "status": status,
        }
    except Exception as err:
        logger.exception(
            "Node level exception. %s",
            err,
            extra={"requestId": state.requestId, "nodeName": "generalChatNode"},
        )
        raise

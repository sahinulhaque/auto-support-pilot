# utility.py

from typing import Annotated, Any, Literal, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


INTENTS = ["Sales", "Support", "General"]


class GraphContext(BaseModel):
    llm: Any  # This for nodes to access llm


class OrderDetails(BaseModel):
    orderId: Optional[str]
    orderItem: Optional[str]


class GraphState(BaseModel):
    """Langchain Graph state for node."""

    history: Annotated[
        Optional[list[BaseMessage]],
        add_messages,
        Field(description="Langgrah chat history"),
    ]
    context: Annotated[Optional[list[str]], Field(description="RAG list of documents")]
    response: Annotated[Optional[str], Field(description="Response message from AI")]
    intent: Annotated[Optional[str], Field(description="Langgraph status of a node")]
    summary: Annotated[
        Optional[str], Field(description="AI 1-sentence summary of the request")
    ]
    order: Annotated[
        Optional[OrderDetails],
        Field(description="Order items for sales in the request"),
    ]
    status: Annotated[str, Field(description="Langgraph status of a node")]
    userId: Annotated[str, Field(description="The user id from client.")]
    requestId: Annotated[str, Field(description="The request id from fast api.")]
    query: Annotated[
        str, Field(description="The user message or question to AI")
    ]  # User input


class InterruptState(BaseModel):
    requestId: Annotated[str, Field(description="The request id from fast api.")]
    assistantQuery: Annotated[
        Optional[str], Field(description="During interrupt assistant asking question.")
    ]
    userResponse: Annotated[
        Optional[str],
        Field(
            description="The user respond to assistant question. User may choose among options. User may provide order id or purchased item or date of order or any information about a order."
        ),
    ]


SOCKET_STATUS = Literal["stop", "interrupted", "chat"]


class SocketRequest(BaseModel):
    """User request from websocket"""

    userId: Annotated[str, Field(description="The user id using uuid4.")]
    requestId: Annotated[
        Optional[str], Field(description="The request id using uuid4.")
    ]
    userName: Annotated[
        Optional[str], Field(description="The name of the user of current session.")
    ]
    message: Annotated[
        str,
        Field(
            description="The message from the user. User may ask a question or request for information."
        ),
    ]
    status: Annotated[SOCKET_STATUS, Field(description="Request status")]


class SocketResponse(BaseModel):
    """AI response to websocket"""

    status: SOCKET_STATUS
    content: str


# Nodes level


class IndentSchema(BaseModel):
    """Identify the intent of user and other values of the fields."""

    summary: Annotated[
        str, Field(description="A 1-sentence summary of the user input.")
    ]
    intent: Annotated[
        Literal["Sales", "Support", "General"],
        Field(description="The primary category of the request."),
    ]
    orderId: Annotated[
        Optional[str],
        Field(description="This is Order Id or Order Number or Bill Number."),
    ]
    orderItem: Annotated[
        Optional[str],
        Field(description="The specific product or service the user mentioned."),
    ]
    reasoning: Annotated[str, Field(description="Logic behind this classification.")]

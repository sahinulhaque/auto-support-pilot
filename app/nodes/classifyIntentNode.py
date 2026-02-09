# classifyIntentNode.py

import logging
from app.utility import GraphContext, GraphState, IndentSchema, OrderDetails
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


async def classifyIntentNode(
    state: GraphState, runtime: Runtime[GraphContext]
) -> GraphState:
    """This node extracts intent classifications variables"""
    try:
        logger.info("Starting classifyIntentNode Node...")
        systemPrompt = """
### ROLE
You are a High-Precision Intent Classifier and Entity Extractor. Your output determines the routing of a mission-critical workflow.

### STEP-BY-STEP PROCESS
1. **Analyze**: Read the input carefully.
2. **Summarize**: Write a 1-sentence objective summary of the user's core request.
3. **Classify**: Based on the summary, select the most appropriate Intent.
4. **Extract**: Identify any orderId or orderItem mentioned.

### INTENT DEFINITIONS
- **Sales**: Triggered when the user asks about availability, price, location, stock levels, or tracking of a specific order/item. 
  *Requires: orderItem and/or orderId.*
- **Support**: Triggered when the user has a technical problem, needs a manual, asks "How-to", or reports a bug. 
  *Requires: RAG-based document retrieval.*
- **General**: Triggered for greetings, feedback, jokes, or non-business queries.

### EXTRACTION RULES
1. **orderId**: Extract alphanumeric strings following "order", "bill", "#", or "number". (e.g., "ORD-99", "12345").
2. **orderItem**: Extract the primary noun phrase representing a product or service. (e.g., "leather belt", "premium subscription").

### CLASSIFICATION STRATEGY (Few-Shot)
- User: "Where is my order #552?" 
  -> Intent: Sales | orderId: "552" | orderItem: None
- User: "The belt I bought is broken, how do I fix it?" 
  -> Intent: Support | orderId: None | orderItem: "belt" (Note: 'fix' implies Support)
- User: "Do you have any blue jackets in stock?" 
  -> Intent: Sales | orderId: None | orderItem: "blue jackets"
- User: "Hi there, hope you're having a good day!" 
  -> Intent: General | orderId: None | orderItem: None

### CONSTRAINTS
- NEVER guess an orderId if not explicitly provided.
- If the user mentions an item BUT is asking "How to use" it, classify as **Support**.
- If the user is checking "Where is" it, classify as **Sales**.
"""

        llm = runtime.context.llm
        structured_llm = llm.with_structured_output(IndentSchema).with_config(
            configurable={"output_max_token": 1500}
        )

        aiResponse = IndentSchema.model_validate(
            await structured_llm.ainvoke(
                [("system", systemPrompt), ("user", state.query)]
            ),
            extra="ignore",
        )
        state.intent = aiResponse.intent
        state.order = OrderDetails(
            orderId=aiResponse.orderId, orderItem=aiResponse.orderItem
        )
        state.summary = f"Summary: {aiResponse.summary} | Order Id: {aiResponse.orderId} | Item: {aiResponse.orderItem}"
        state.status = "classify intent finished"
        logger.info(
            f"""
        Classification successfull.\n
        Intent: {aiResponse.intent}\n
        Summary: {aiResponse.summary}\n
        Reasoning: {aiResponse.reasoning}
        """
        )
        logger.info("Node status: %s", state.status)
        return state
    except Exception as err:
        logger.exception(
            "Node level exception. %s",
            err,
            extra={"requestId": state.requestId, "nodeName": "classifyIndentNode"},
        )
        raise

# salesNode.py

from functools import cached_property
import logging
import os
from pathlib import Path
import aiosqlite
from dotenv import load_dotenv
from app.utility import GraphContext, GraphState, OrderDetails
from langgraph.runtime import Runtime
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain.messages import AIMessage, HumanMessage

load_dotenv()
logger = logging.getLogger(__name__)


async def salesNode(state: GraphState, runtime: Runtime[GraphContext]) -> dict:
    """Fetch orders from database and used as context to AI"""
    try:

        db = SqlDb()
        await db.setup
        orderList = await db.fetch_orders(state.order)
        state.context = [
            f"Item: {r['orderItem']} | ID: {r['orderId']} | Status: {r['status']} | Loc: {r['location']}"
            for r in (orderList or [])
        ]
        formattedOrders = (
            "\n".join(state.context) if orderList else "No matching order data found."
        )

        systemPrompt = """
ROLE: You are an expert Sales Executive. Your name is Salma Hussian.
CONTEXT: Use the following database records to answer the user:
{formatted_orders}

INSTRUCTIONS:
1. Be professional, helpful, and concise.
2. If the order is found, provide the status and location clearly.
3. If no data is found, apologize and ask for a valid Order ID or Item name.
4. Answer only based on the provided context.
"""

        prompt = ChatPromptTemplate(
            [
                ("system", systemPrompt),
                MessagesPlaceholder("history"),
                ("user", "{input}"),
            ]
        )
        model = runtime.context.llm.with_config(configurable={"output_max_token": 100})
        chain = prompt | model | StrOutputParser()

        aiResponse = await chain.ainvoke(
            {
                "formatted_orders": formattedOrders,
                "input": state.query,
                "history": state.history or [],
            }
        )

        status = "sales completed"
        logger.info("Sales state: %s", status)
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
            "Node level exception %s",
            err,
            extra={"requestId": state.requestId, "nodeName": "salesNode"},
        )
        raise


class SqlDb:
    def __init__(self) -> None:
        self.__dbPath = Path(os.getenv("SQLDB_PATH", "sqldb/inventory.db"))

    @cached_property
    async def setup(self):
        try:
            folder = self.__dbPath.parent
            folder.mkdir(parents=True, exist_ok=True)
            async with aiosqlite.connect(self.__dbPath) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
SELECT COUNT(name) AS total 
FROM sqlite_master 
WHERE type='table' 
AND name NOT LIKE 'sqlite_%' 
AND name NOT LIKE '%_fts%';
                """
                )
                tableCount = await cursor.fetchone()

                if tableCount and tableCount["total"] > 0:
                    return

                # create default table and dummy data
                await db.execute(
                    """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orderId TEXT, orderItem TEXT, status TEXT, location TEXT
);
"""
                )
                mock_data = [
                    ("ORD-001", "Laptop", "Delivered", "Hyderabad"),
                    ("ORD-002", "Belt", "Processing", "Shop"),
                    ("ORD-003", "Jacket", "Delivered", "Kolkata"),
                    ("ORD-004", "Wallet", "In Stock", "Store 2"),
                    ("ORD-005", "Bag", "Shipped", "Warehouse B"),
                ]
                await db.executemany(
                    "INSERT INTO orders (orderId, orderItem, status, location) VALUES (?, ?, ?, ?)",
                    mock_data,
                )
                await db.commit()
        except Exception as err:
            logger.exception(
                "SQL Db level exception %s",
                err,
                extra={"nodeName": "salesNode"},
            )

    async def fetch_orders(self, order: OrderDetails | None):
        try:
            query = "SELECT orderId, orderItem, status, location FROM orders WHERE 1=1"
            params = []
            if order and order.orderId:
                query += " AND orderId = ?"
                params.append(order.orderId)
            if order and order.orderItem:
                query += " AND orderItem LIKE ?"
                params.append(f"%{order.orderItem}%")

            async with aiosqlite.connect(self.__dbPath) as db:
                db.row_factory = aiosqlite.Row
                orderList = await db.execute_fetchall(f"{query} LIMIT 5", params)
                if orderList:
                    return [dict(row) for row in orderList]
        except Exception as err:
            logger.exception(
                "SQL Db level exception %s",
                err,
                extra={"nodeName": "salesNode"},
            )

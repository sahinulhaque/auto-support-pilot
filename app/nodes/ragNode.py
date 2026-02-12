# ragNode.py

from functools import cached_property
import logging
import os
import dotenv
from app.utility import GraphContext, GraphState
from langgraph.runtime import Runtime
from langchain_chroma import Chroma
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    TextLoader,
)
from pathlib import Path

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


async def ragNode(state: GraphState, runtime: Runtime[GraphContext]) -> dict:
    """RAG retrive company policy and information from vector db"""
    try:

        vdb = VectorDb()
        ragContext = await vdb.search(state.query)
        formattedRag = "\n".join(f"-{d}" for d in ragContext)

        systemPrompt = """
System: You are an expert Customer Support Executive. Your name is Ashma Khan.
Your goal is to:
1. Solve the user's problem effectively.
2. Answer their questions accurately using only the provided context.

Context:
{support_context}

Instructions:
- If the context doesn't contain the answer, politely inform the user.
- Maintain a professional, helpful, and concise tone.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", systemPrompt),
                MessagesPlaceholder(variable_name="history"),
                ("user", "{input}"),
            ]
        )

        model = runtime.context.llm.with_config(
            configurable={
                "output_max_token": 500,
            }
        )
        chain = prompt | model | StrOutputParser()

        aiResponse = await chain.ainvoke(
            {
                "history": state.history or [],
                "support_context": formattedRag,
                "input": state.query,
            }
        )

        status = "rag node finished"
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
            extra={"requestId": state.requestId, "nodeName": "ragNode"},
        )
        raise


class VectorDb:
    def __init__(self, collection: str = "") -> None:
        self.__collection = collection or "rag_collection"
        self.__embedModel = "BAAI/bge-small-en-v1.5"
        self.__dbPath = Path(os.getenv("VECTORDB_PATH", "chromedb"))
        self.__documentsPath = Path(
            os.getenv("VECTORDB_DOCUMENT_PATH", "chromaDocuments")
        )
        if self.getTotalDocuments <= 0:
            self.__insertDocs()

    @cached_property
    def __embeddings(self) -> FastEmbedEmbeddings:
        return FastEmbedEmbeddings(model_name=self.__embedModel)

    @cached_property
    def __db(self) -> Chroma:
        """Cache embedding chroma db"""
        folder = self.__dbPath.parent
        folder.mkdir(parents=True, exist_ok=True)

        return Chroma(
            collection_name=self.__collection,
            embedding_function=self.__embeddings,
            persist_directory=str(self.__dbPath),
            collection_metadata={"hnsw:space": "cosine"},
        )

    @property
    def getTotalDocuments(self):
        return self.__db._collection.count()

    def __insertDocs(self):
        """
        Upsert all docs within folder /chromaDocuments into db.
        This will run only when vector db is empty.
        """
        try:
            folder = self.__documentsPath

            if not folder.exists():
                logger.info("Rag Vector DB: Document folder is don't exists.")
                return

            for filePath in folder.iterdir():
                ext = filePath.suffix.lower()
                if (
                    not filePath.exists(follow_symlinks=False)
                    or not filePath.is_file()
                    or ext not in (".doc", ".pdf", ".txt", ".md")
                ):
                    continue

                if ext == ".pdf":
                    loader = PyPDFLoader(
                        file_path=str(filePath),
                    )
                elif ext == ".doc":
                    loader = UnstructuredWordDocumentLoader(filePath)
                else:
                    loader = TextLoader(filePath, encoding="utf-8")

                documents = loader.load()
                if len(documents) > 0:
                    ids = self.__db.add_documents(documents)
                    logger.info(
                        f"Rag Vector DB: Total {len(ids)} documents created from {filePath.name}"
                    )

        except Exception as err:
            logger.exception(
                "Rag Vector DB level exception. %s",
                err,
                extra={"nodeName": "ragNode"},
            )
            raise

    async def search(self, query: str, ktop: int = 2) -> list[str]:
        """Query vector search"""
        documents = await self.__db.asimilarity_search(query=query, k=ktop)
        return [d.page_content for d in documents]

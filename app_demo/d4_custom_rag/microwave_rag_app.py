from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings, AzureChatOpenAI, AzureOpenAIEmbeddings
from pydantic import SecretStr

import uvicorn

from aidial_sdk import DIALApp
from aidial_sdk.chat_completion import ChatCompletion, Request, Response


SYSTEM_PROMPT = """You are a RAG-powered assistant that assists users with their questions about microwave usage.
            
## Structure of User message:
`RAG CONTEXT` - Retrieved documents relevant to the query.
`USER QUESTION` - The user's actual question.

## Instructions:
- Use information from `RAG CONTEXT` as context when answering the `USER QUESTION`.
- Cite specific sources when using information from the context.
- Answer ONLY based on conversation history and RAG context.
- If no relevant information exists in `RAG CONTEXT` or conversation history, state that you cannot answer the question.
"""

USER_PROMPT = """##RAG CONTEXT:
{context}


##USER QUESTION: 
{query}"""


class MicrowaveRagApplication(ChatCompletion):

    def __init__(self, embeddings: OpenAIEmbeddings, llm_client: AzureChatOpenAI):
        self.llm_client = llm_client
        self.embeddings = embeddings
        self.vectorstore = self._setup_vectorstore()

    def _setup_vectorstore(self) -> VectorStore:
        loader = TextLoader('microwave_manual.txt', encoding='utf-8')
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,
            chunk_overlap=50,
            separators=["\n\n", "\n", "."]
        )
        chunks = text_splitter.split_documents(documents)

        return FAISS.from_documents(chunks, self.embeddings)

    async def chat_completion(
            self, request: Request, response: Response
    ) -> None:
        last_user_message = request.messages[-1]

        with response.create_single_choice() as choice:
            print(f"Last user message: {last_user_message}")

            context = self.retrieve_context(last_user_message.content)

            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=USER_PROMPT.format(context=context, query=last_user_message.content))
            ]

            for chunk in self.llm_client.stream(messages):
                if chunk.content:
                    choice.append_content(chunk.content)

    def retrieve_context(self, query: str, k: int = 4, score=0.3):
        relevant_docs = self.vectorstore.similarity_search_with_relevance_scores(
            query,
            k=k,
            score_threshold=score
        )

        context_parts = []
        for (doc, score) in relevant_docs:
            context_parts.append(doc.page_content)

        return "\n\n".join(context_parts)

custom_rag_app = MicrowaveRagApplication(
    embeddings=AzureOpenAIEmbeddings(
        azure_endpoint="http://localhost:8080",
        deployment='text-embedding-3-large',
        api_key=SecretStr('dial_api_key'),
    ),
    llm_client=AzureChatOpenAI(
        azure_endpoint="http://localhost:8080",
        azure_deployment='gpt-4o',
        api_key=SecretStr('dial_api_key'),
        api_version="2024-08-06"
    )
)

app = DIALApp()
app.add_chat_completion("microwave-rag", custom_rag_app)

if __name__ == "__main__":
    uvicorn.run(app, port=5028, host="0.0.0.0")

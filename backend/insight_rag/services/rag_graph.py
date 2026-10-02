from typing import TypedDict

from langgraph.graph import END, StateGraph

from insight_rag.schemas.chat import SearchHit
from insight_rag.services.llm import chat_completion
from insight_rag.services.multimodal_retrieval_service import retrieve_multimodal_chunks


class RagState(TypedDict):
    knowledge_base_id: int
    question: str
    rewritten_query: str
    top_k: int
    rerank: bool
    retrieval_mode: str
    db: object
    hits: list[SearchHit]
    answer: str
    answer_messages: list[dict[str, str]]


async def rewrite_query(state: RagState) -> RagState:
    prompt = [
        {"role": "system", "content": "Rewrite the user question into a concise retrieval query. Return only the query."},
        {"role": "user", "content": state["question"]},
    ]
    try:
        state["rewritten_query"] = (await chat_completion(prompt)).strip() or state["question"]
    except Exception:
        state["rewritten_query"] = state["question"]
    return state


async def retrieve(state: RagState) -> RagState:
    state["hits"] = await retrieve_multimodal_chunks(
        state["db"],
        state["knowledge_base_id"],
        state["rewritten_query"],
        state["top_k"],
        rerank=state["rerank"],
    )
    return state


async def optional_rerank(state: RagState) -> RagState:
    return state


async def generate_answer(state: RagState) -> RagState:
    context = "\n\n".join(
        (
            f"[chunk_id={hit.chunk_id} doc_id={hit.document_id} "
            f"filename={hit.metadata.get('filename')} page={hit.metadata.get('page_number')} "
            f"source_type={hit.metadata.get('source_type')} image_url={hit.metadata.get('image_url') or hit.metadata.get('public_url')} "
            f"figure={hit.metadata.get('figure')}]\n{hit.content}"
        )
        for hit in state["hits"]
    )
    state["answer_messages"] = [
        {
            "role": "system",
            "content": (
                "You are an enterprise RAG assistant. Answer in the user's language. "
                "Use only the provided context. If context is insufficient, say so clearly. "
                "Always include citations using chunk ids and source filenames from the context when useful. "
                "For image evidence, cite the figure/page and image_url when available."
            ),
        },
        {"role": "user", "content": f"Question:\n{state['question']}\n\nContext:\n{context}"},
    ]
    return state


async def finalize(state: RagState) -> RagState:
    return state


def build_rag_graph():
    graph = StateGraph(RagState)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("optional_rerank", optional_rerank)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("rewrite_query")
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("retrieve", "optional_rerank")
    graph.add_edge("optional_rerank", "generate_answer")
    graph.add_edge("generate_answer", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


rag_graph = build_rag_graph()


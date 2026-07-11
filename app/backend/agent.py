"""LangGraph agent: route -> retrieve -> (gate) -> generate -> judge -> finalize.

The graph is the explainable spine of the system: each node is a discrete, logged step.
Generation is grounded strictly in retrieved context and cites its sources; the evidence
gate refuses when retrieval finds nothing relevant; the groundedness judge and re-rank
relevance combine into the confidence score shown to the supervisor.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TypedDict

import structlog
from langgraph.graph import END, StateGraph

from app.backend.judge import judge_groundedness
from app.backend.llm import chat
from app.backend.retriever import Passage, Retriever
from app.backend.schemas import AgentResponse, Citation, confidence_from_score
from app.backend.settings import BackendSettings, load_backend_settings

log = structlog.get_logger("agent")

_GEN_SYSTEM = (
    "You are a plant-floor documentation assistant. Answer the supervisor's question "
    "using ONLY the numbered CONTEXT passages. Rules:\n"
    "- Ground every statement in the context. Do not add outside knowledge.\n"
    "- Cite the passages you use inline as [1], [2], matching the passage numbers.\n"
    "- Be concise and practical; use short steps or bullets when it helps.\n"
    "- If the context does not contain the answer, say you don't have documentation "
    "covering it — do not guess."
)


class AgentState(TypedDict, total=False):
    question: str
    domain: str | None
    passages: list[Passage]
    answer: str
    relevance: float
    groundedness: float
    response: AgentResponse


@lru_cache(maxsize=1)
def _settings() -> BackendSettings:
    return load_backend_settings()


@lru_cache(maxsize=1)
def _retriever() -> Retriever:
    return Retriever(_settings())


def _context_block(passages: list[Passage]) -> str:
    """Render retrieved passages as a numbered context block for the LLM."""
    blocks = []
    for i, p in enumerate(passages, start=1):
        m = p.metadata
        head = f"[{i}] {m.get('title', 'Source')} - {m.get('section', '')} (p.{m.get('page')})"
        blocks.append(f"{head}\n{p.text}")
    return "\n\n".join(blocks)


def _citations(passages: list[Passage]) -> list[Citation]:
    """Dedupe passages into citations by (title, section, page)."""
    seen: set[tuple] = set()
    out: list[Citation] = []
    for p in passages:
        m = p.metadata
        key = (m.get("title"), m.get("section"), m.get("page"))
        if key in seen:
            continue
        seen.add(key)
        snippet = p.text.strip().replace("\n", " ")
        out.append(
            Citation(
                source_title=m.get("title", "Source"),
                section=m.get("section") or None,
                page=m.get("page"),
                url=m.get("url"),
                snippet=(snippet[:160] + "...") if len(snippet) > 160 else snippet,
            )
        )
    return out


# --- Graph nodes ---

def route_node(state: AgentState) -> AgentState:
    from app.backend.router import route  # local import keeps router optional in tests

    domain = route(_settings(), state["question"])
    log.info("route", question=state["question"][:80], domain=domain)
    return {"domain": domain}


def retrieve_node(state: AgentState) -> AgentState:
    result = _retriever().retrieve(state["question"], domain=state.get("domain"))
    log.info(
        "retrieve",
        domain=state.get("domain"),
        n=len(result.passages),
        relevance=round(result.relevance, 3),
    )
    return {"passages": result.passages, "relevance": result.relevance}


def generate_node(state: AgentState) -> AgentState:
    passages = state["passages"]
    context = _context_block(passages)
    user = f"QUESTION:\n{state['question']}\n\nCONTEXT:\n{context}"
    answer = chat(
        _settings(),
        messages=[
            {"role": "system", "content": _GEN_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        max_tokens=800,
    )
    log.info("generate", chars=len(answer))
    return {"answer": answer}


def judge_node(state: AgentState) -> AgentState:
    context = _context_block(state["passages"])
    g = judge_groundedness(_settings(), state["question"], state["answer"], context)
    log.info("judge", supported=g.supported, score=g.score)
    return {"groundedness": g.score}


def finalize_node(state: AgentState) -> AgentState:
    # Composite confidence = retrieval relevance x answer groundedness.
    score = state.get("relevance", 0.0) * state.get("groundedness", 0.0)
    # Only cite when we're actually grounding an answer; a near-zero score means the
    # model refused despite the (irrelevant) context, so citations would be spurious.
    answer = state["answer"]
    if score >= 0.15:
        citations = _citations(state["passages"])
        domain = state.get("domain") or "unrouted"
    else:
        citations = []
        domain = "unrouted"
        answer = re.sub(r"\s*\[\d+\]", "", answer)  # strip dangling [n] markers

    response = AgentResponse(
        answer=answer,
        domain=domain,
        confidence=confidence_from_score(score),
        citations=citations,
    )
    return {"response": response}


def gate_node(state: AgentState) -> AgentState:
    """No relevant evidence -> refuse rather than answer weakly."""
    log.info("evidence_gate", domain=state.get("domain"))
    response = AgentResponse(
        answer=(
            "I don't have documentation covering that. I can answer questions about "
            "safety procedures, equipment maintenance, or quality-control standards — "
            "try rephrasing, or ask about one of those."
        ),
        domain=state.get("domain") or "unrouted",
        confidence=confidence_from_score(0.0),
        citations=[],
    )
    return {"response": response}


def _has_evidence(state: AgentState) -> str:
    return "generate" if state.get("passages") else "gate"


@lru_cache(maxsize=1)
def _graph():
    """Build and compile the agent graph once."""
    g = StateGraph(AgentState)
    g.add_node("route", route_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("generate", generate_node)
    g.add_node("judge", judge_node)
    g.add_node("finalize", finalize_node)
    g.add_node("gate", gate_node)

    g.set_entry_point("route")
    g.add_edge("route", "retrieve")
    g.add_conditional_edges("retrieve", _has_evidence, {"generate": "generate", "gate": "gate"})
    g.add_edge("generate", "judge")
    g.add_edge("judge", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("gate", END)
    return g.compile()


def answer_question(question: str) -> AgentResponse:
    """Run the full agent graph and return the response payload."""
    final = _graph().invoke({"question": question})
    return final["response"]

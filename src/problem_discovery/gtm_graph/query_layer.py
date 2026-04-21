from __future__ import annotations

from langchain.chains import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain_community.graphs import Neo4jGraph


def build_graph_rag_chain(
    uri: str,
    username: str,
    password: str,
    model_name: str = "gpt-4o",
    temperature: float = 0.0,
) -> GraphCypherQAChain:
    graph = Neo4jGraph(url=uri, username=username, password=password)
    llm = ChatOpenAI(model=model_name, temperature=temperature)
    return GraphCypherQAChain.from_llm(
        llm,
        graph=graph,
        verbose=True,
        return_intermediate_steps=True,
    )


def ask_graph_chain(chain: GraphCypherQAChain, question: str) -> dict[str, object]:
    return chain.invoke(question)

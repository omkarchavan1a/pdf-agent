from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
from llm_setup import get_gemma_llm

class AgentState(TypedDict):
    input_query: str
    context: str
    result: str

def summarize_node(state: AgentState) -> Dict[str, Any]:
    llm = get_gemma_llm()
    prompt = f"Summarize the following document excerpts for an executive overview:\n\n{state['context']}"
    try:
        res = llm.invoke(prompt)
    except Exception as e:
        res = f"Error during summarization: {str(e)}"
    return {"result": res}

def search_node(state: AgentState) -> Dict[str, Any]:
    llm = get_gemma_llm()
    prompt = f"Answer the user query based on the provided document excerpts.\nQuery: {state['input_query']}\nContext:\n{state['context']}\nAnswer:"
    try:
        res = llm.invoke(prompt)
    except Exception as e:
        res = f"Error during search: {str(e)}"
    return {"result": res}

def route_query(state: AgentState) -> str:
    if "summarize" in state["input_query"].lower():
        return "summarize"
    return "search"

def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("search", search_node)
    
    workflow.set_conditional_entry_point(
        route_query,
        {
            "summarize": "summarize",
            "search": "search"
        }
    )
    
    workflow.add_edge("summarize", END)
    workflow.add_edge("search", END)
    
    return workflow.compile()

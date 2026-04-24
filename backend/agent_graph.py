from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, END
try:
    # Package import path.
    from .llm_setup import get_gemma_llm
except ImportError:
    # Script-mode fallback.
    from llm_setup import get_gemma_llm

class AgentState(TypedDict):
    input_query: str
    context: str
    result: str

EDIT_INSTRUCTION = """
If the user asks to 'add a note', 'edit', 'comment', or 'mark' the document:
1. Provide a helpful textual confirmation in your response.
2. Add a special tag at the very end: [[EDIT: Page X | Character-limited summary of the edit]]
   - X is the page number (default to 1).
   - The content should be the text of the sticky note to be placed on the PDF.
"""

def summarize_node(state: AgentState) -> Dict[str, Any]:
    llm = get_gemma_llm()
    prompt = f"Summarize the following document excerpts for an executive overview:\n\n{state['context']}\n\n{EDIT_INSTRUCTION}"
    try:
        res = llm.invoke(prompt)
    except Exception as e:
        res = f"Error during summarization: {str(e)}"
    return {"result": res}

def search_node(state: AgentState) -> Dict[str, Any]:
    llm = get_gemma_llm()
    prompt = f"Answer the user query based on the provided document excerpts.\nQuery: {state['input_query']}\nContext:\n{state['context']}\n\n{EDIT_INSTRUCTION}\nAnswer:"
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

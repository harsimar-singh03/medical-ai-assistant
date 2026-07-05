"""RAG Pipeline — Simple 2-stage retrieval with corrective rewriting."""

import os
from langchain_groq import ChatGroq
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel, Field

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)

CHUNK_SIZE    = 500
CHUNK_OVERLAP = 100
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH      = os.path.join(BASE_DIR, "data", "diseases.pdf")

_vector_db = None

import streamlit as st
import os
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass


#Vector DB 
def build_vector_db():
    global _vector_db
    if _vector_db is not None:
        return _vector_db

    reader = PdfReader(PDF_PATH)
    full_text = "".join(page.extract_text() + "\n" for page in reader.pages if page.extract_text())

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks   = splitter.create_documents([full_text])

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    _vector_db = FAISS.from_documents(chunks, embeddings)
    return _vector_db

#  Relevance scoring (Pydantic) 
class RelevanceScore(BaseModel):
    score: int = Field(ge=0, le=10)

_scoring_llm = llm.with_structured_output(RelevanceScore)

def _relevance(query: str, doc: str) -> float:
    prompt = f"""Query: "{query}"
Document excerpt: "{doc[:400]}"
Rate relevance 0-10. Return ONLY the number."""
    try:
        return _scoring_llm.invoke(prompt).score / 10.0
    except Exception:
        return 0.5

#  Query rewriting 
def _rewrite(original: str) -> str:
    prompt = f"""Rewrite this patient query for a medical textbook search.
Use medical terminology, 5-10 words. Return ONLY the rewritten query.
Original: "{original}" """
    try:
        return llm.invoke(prompt).content.strip()
    except Exception:
        return original

#  Main search 
def search_medical_knowledge(query: str, k: int = 5):
    db       = build_vector_db()
    docs     = db.similarity_search(query, k=k)
    contexts = [d.page_content for d in docs]

    if contexts and _relevance(query, contexts[0]) >= 0.5:
        return contexts

    # Stage 2: rewrite & retry
    rewritten = _rewrite(query)
    docs2     = db.similarity_search(rewritten, k=k)
    return [d.page_content for d in docs2] if docs2 else contexts   

def get_relevant_context(symptoms: str) -> list[str]:
    return search_medical_knowledge(symptoms.strip())
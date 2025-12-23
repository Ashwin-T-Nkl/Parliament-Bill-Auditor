import streamlit as st
from pypdf import PdfReader
import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from langchain_groq import ChatGroq

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Parliament Bill Auditor", layout="wide")
st.title("🏛️ Parliament Bill Auditor")

# ---------------- SESSION STATE ----------------
if "view" not in st.session_state:
    st.session_state.view = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "last_file" not in st.session_state:
    st.session_state.last_file = None
if "full_text" not in st.session_state:
    st.session_state.full_text = ""

# ---------------- AGGRESSIVE TEXT CLEANING ----------------
def deep_clean_text(text):
    # 1. Remove or [123] patterns
    text = re.sub(r'\[.*?\]', '', text)
    # 2. Remove literal backslashes (Fixes your previous SyntaxError)
    text = text.replace('\\', '')
    # 3. Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.view = None
        
        reader = PdfReader(uploaded_file)
        raw_text = ""
        for page in reader.pages:
            try:
                content = page.extract_text()
                if content: raw_text += content + "\n"
            except: pass
        
        # Clean the text to remove the "Number Trigger"
        st.session_state.full_text = deep_clean_text(raw_text)

    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY.")
        st.stop()

    # Temperature 0.2 helps break loops while staying accurate
    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0.2)

    if st.button("🔍 Generate Analysis"):
        with st.spinner("Analyzing..."):
            prompt = f"""
            You are a Policy Expert. 
            Analyze the Bill text. 
            
            STRICT RULES:
            1. DO NOT output lists of numbers like '1, 2, 3...'.
            2. USE WORDS ONLY for your response.
            3. If info is missing, say 'Not Found'.
            4. Start your response exactly with the word: 'ANALYSIS:'

            HEADINGS TO USE:
            SECTOR:
            OBJECTIVE:
            SIMPLE SUMMARY:
            DETAILED SUMMARY:
            IMPACT ANALYSIS:
            POSITIVES:
            NEGATIVES / RISKS:

            TEXT: {st.session_state.full_text[:15000]}
            """
            response = llm.invoke(prompt)
            # Remove the "ANALYSIS:" prefix for display
            st.session_state.analysis = response.content.replace("ANALYSIS:", "").strip()
            st.session_state.view = None

# ---------------- HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content or title not in content:
        return "Not available."
    parts = content.split(title)
    if len(parts) > 1:
        # Stop reading at the next newline that looks like a heading
        text = re.split(r'\n[A-Z\s]+:', parts[1])[0]
        return text.strip()
    return "Not found."

# ---------------- NAVIGATION & DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    if c1.button("🏷️ Sector"): st.session_state.view = "sector"
    if c2.button("📄 Summary"): st.session_state.view = "summary"
    if c3.button("📊 Impact"): st.session_state.view = "impact"

    st.markdown("---")
    if st.session_state.view == "sector":
        st.info(extract("SECTOR:"))
    elif st.session_state.view == "summary":
        st.subheader("Objective")
        st.write(extract("OBJECTIVE:"))
        st.subheader("Detailed Summary")
        st.write(extract("DETAILED SUMMARY:"))
    elif st.session_state.view == "impact":
        st.success(f"Positives: {extract('POSITIVES:')}")
        st.error(f"Risks: {extract('NEGATIVES / RISKS:')}")

# ---------------- CHAT ----------------
if st.session_state.analysis:
    st.header("💬 Ask a Question")
    user_q = st.text_input("Example: Who proposed this bill?")
    if user_q:
        chat_prompt = f"""
        Answer using the Bill text. 
        DO NOT use numbers or source tags. 
        Use complete sentences.
        If not found, say 'Not in document'.
        
        TEXT: {st.session_state.full_text[:15000]}
        QUESTION: {user_q}
        """
        st.chat_message("assistant").write(llm.invoke(chat_prompt).content)

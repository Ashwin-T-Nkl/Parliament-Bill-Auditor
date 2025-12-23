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

# ---------------- TEXT CLEANING HELPER ----------------
def clean_pdf_text(text):
    """Removes tags which cause the AI to output numbers."""
    return re.sub(r'\', '', text)

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
                if content:
                    raw_text += content + "\n"
            except:
                pass
        
        # FIX 1: Clean the text immediately after extraction
        st.session_state.full_text = clean_pdf_text(raw_text)

    if "GROQ_API_KEY" not in os.environ:
        st.error("AI service not configured. Please set GROQ_API_KEY.")
        st.stop()

    # FIX 2: Set temperature to 0.1 to avoid repetitive looping
    llm = ChatGroq(
        model_name="llama-3.1-8b-instant",
        temperature=0.1 
    )

    if st.button("🔍 Generate Analysis"):
        with st.spinner("Analyzing bill..."):
            prompt = f"""
You are a Public Policy Analyst. 
Audience: 8th grade students. Use very simple language.

Rules:
- DO NOT output long lists of numbers or source indices.
- DO NOT use markdown symbols like ** or ###.
- Use only the provided text.

Return exactly these headings:
SECTOR:
OBJECTIVE:
SIMPLE SUMMARY:
DETAILED SUMMARY:
IMPACT ANALYSIS:
BENEFICIARIES:
AFFECTED GROUPS:
POSITIVES:
NEGATIVES / RISKS:

BILL TEXT:
{st.session_state.full_text[:20000]}
"""
            response = llm.invoke(prompt)
            st.session_state.analysis = response.content
            st.session_state.view = None

# ---------------- NAVIGATION ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.markdown("### 📌 Explore Analysis")
    c1, c2, c3 = st.columns(3)
    if c1.button("🏷️ Sector"): st.session_state.view = "sector"
    if c2.button("📄 Summary"): st.session_state.view = "summary"
    if c3.button("📊 Impact"): st.session_state.view = "impact"

# ---------------- HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content or title not in content:
        return "Not mentioned in document."
    
    parts = content.split(title)
    if len(parts) > 1:
        # Get text until the next uppercase heading
        text = re.split(r'\n[A-Z\s/]+:', parts[1])[0]
        return text.strip()
    return "Not available."

def generate_summary_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica", 10)
    for line in text.split("\n"):
        if y < 40:
            pdf.showPage()
            y = 800
        pdf.drawString(40, y, line[:100])
        y -= 14
    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- CONTENT DISPLAY ----------------
st.markdown("---")
if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.info(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Bill Summary")
    st.subheader("🎯 Objective")
    st.write(extract("OBJECTIVE:"))
    st.subheader("💡 Simple Overview")
    st.write(extract("SIMPLE SUMMARY:"))
    with st.expander("📘 View Detailed Summary"):
        detail = extract("DETAILED SUMMARY:")
        st.write(detail)
        st.download_button("⬇️ Download PDF", generate_summary_pdf(detail), "Summary.pdf")

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")
    st.write(extract("IMPACT ANALYSIS:"))
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("✅ Positives")
        st.success(extract("POSITIVES:"))
    with col_b:
        st.subheader("⚠️ Risks")
        st.error(extract("NEGATIVES / RISKS:"))

# ---------------- AI CHAT ----------------
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    user_q = st.text_input("Ask a question:")

    if user_q:
        with st.spinner("Thinking..."):
            # FIX 3: Strict Chat Prompt
            chat_prompt = f"""
            Answer the question using the Bill text. 
            If not mentioned, say 'Not mentioned in the document'.
            DO NOT output numbers or tokens. Use full sentences.

            BILL TEXT:
            {st.session_state.full_text[:20000]}

            QUESTION:
            {user_q}
            """
            answer = llm.invoke(chat_prompt)
            st.chat_message("assistant").write(answer.content)

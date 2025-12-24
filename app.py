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

# ---------------- ROBUST VALIDATION ----------------
BILL_KEYWORDS = [
    "bill", "act", "parliament", "lok sabha", "rajya sabha", "gazette", 
    "legislative", "enacted", "item no", "clause", "minister", "ministry",
    "objects and reasons", "viniyamit", "vidheyak" # Added Hindi phonetic keywords
]

def clean_text(text):
    """Removes tags and excessive whitespace."""
    text = re.sub(r'\', '', text)
    return ' '.join(text.split())

def is_valid_doc(text):
    """Forgiving check: Pass if text is long enough and has at least 1 keyword."""
    if len(text.strip()) < 200: return False
    text_lower = text.lower()
    return any(k in text_lower for k in BILL_KEYWORDS)

# ---------------- SESSION STATE ----------------
if "analysis" not in st.session_state: st.session_state.analysis = None
if "full_text" not in st.session_state: st.session_state.full_text = ""
if "last_file" not in st.session_state: st.session_state.last_file = None

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        
        reader = PdfReader(uploaded_file)
        raw_text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t: raw_text += t + "\n"
        st.session_state.full_text = clean_text(raw_text)

    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY.")
        st.stop()

    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

    if st.button("🔍 Generate Analysis"):
        if not is_valid_doc(st.session_state.full_text):
            st.warning("⚠️ Document might not be a standard Bill, but I will try to analyze it anyway.")
        
        with st.spinner("Analyzing document..."):
            prompt = f"""
            You are a Public Policy Analyst for 8th graders.
            Analyze this Bill/Policy text. Use ONLY the text provided.
            Do NOT use markdown symbols like ** or #.

            SECTOR: (Agri/Finance/Education/Healthcare/Tech/Environment/Defence/Other)
            OBJECTIVE: (3-5 lines)
            DETAILED SUMMARY: (10-20 bullets)
            IMPACT ANALYSIS:
            Citizens: (Bullets)
            Businesses: (Bullets)
            Government: (Bullets)
            BENEFICIARIES: (Bullets)
            AFFECTED GROUPS: (Bullets)
            POSITIVES: (Bullets)
            NEGATIVES / RISKS: (Bullets)

            TEXT: {st.session_state.full_text[:18000]}
            """
            response = llm.invoke(prompt)
            st.session_state.analysis = response.content

# ---------------- HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content: return "No data available."
    markers = ["SECTOR:", "OBJECTIVE:", "DETAILED SUMMARY:", "IMPACT ANALYSIS:", 
               "BENEFICIARIES:", "AFFECTED GROUPS:", "POSITIVES:", "NEGATIVES / RISKS:"]
    try:
        start = content.find(title)
        if start == -1: return "Section not found."
        start += len(title)
        end = len(content)
        for m in markers:
            pos = content.find(m, start)
            if pos != -1 and pos < end: end = pos
        return content[start:end].strip()
    except: return "Extraction error."

def generate_summary_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica", 10)
    for line in text.split("\n"):
        if y < 50: pdf.showPage(); y = 800
        pdf.drawString(50, y, line[:95]); y -= 15
    pdf.save(); buffer.seek(0)
    return buffer

# ---------------- CONTENT DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    # Using Tabs for better stability over buttons
    tab1, tab2, tab3 = st.tabs(["🏷️ Sector", "📄 Summary", "📊 Impact"])

    with tab1:
        st.info(extract("SECTOR:"))

    with tab2:
        st.subheader("🎯 Objective")
        st.write(extract("OBJECTIVE:"))
        with st.expander("📘 Detailed Summary", expanded=True):
            detail = extract("DETAILED SUMMARY:")
            st.write(detail)
            st.download_button("⬇️ Download PDF", generate_summary_pdf(detail), "Bill_Summary.pdf")

    with tab3:
        st.subheader("📊 Impact Analysis")
        st.write(extract("IMPACT ANALYSIS:"))
        c_a, c_b = st.columns(2)
        with c_a:
            st.success("✅ Positives\n\n" + extract("POSITIVES:"))
            st.write("**Beneficiaries:**", extract("BENEFICIARIES:"))
        with c_b:
            st.error("⚠️ Risks\n\n" + extract("NEGATIVES / RISKS:"))
            st.write("**Affected Groups:**", extract("AFFECTED GROUPS:"))

# ---------------- AI CHAT ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    q = st.text_input("Ask a specific question:")
    if q:
        with st.spinner("Answering..."):
            ans = llm.invoke(f"Context: {st.session_state.full_text[:10000]}\nQuestion: {q}")
            st.chat_message("assistant").write(ans.content)

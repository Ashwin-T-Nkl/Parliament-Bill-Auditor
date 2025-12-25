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

# ---------------- IMPROVED VALIDATION ----------------
# Added more specific legal and bilingual markers to ensure official docs pass
BILL_KEYWORDS = [
    "bill", "act", "parliament", "lok sabha", "rajya sabha", "gazette", 
    "legislative", "enacted", "minister", "ministry", "objects and reasons",
    "vidheyak", "adhiniyam", "purasthapit", "introduced", "passed", "clause"
]

def is_valid_government_doc(text):
    if len(text.strip()) < 100: return False
    text_lower = text.lower()
    # Require at least 2 keywords to ensure higher validation accuracy
    count = sum(1 for k in BILL_KEYWORDS if k in text_lower)
    return count >= 2

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
            try:
                t = page.extract_text()
                if t: raw_text += t + "\n"
            except: pass
        st.session_state.full_text = raw_text

    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY in secrets.")
        st.stop()

    # MODEL CHANGE: Using 70b-versatile for high reasoning and to stop number-looping
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile", 
        temperature=0.1, 
        max_tokens=3500
    )

    if st.button("🔍 Generate Analysis"):
        if not is_valid_government_doc(st.session_state.full_text):
            st.warning("⚠️ This document might not be a standard Bill, but I will try to analyze it anyway.")
            
        with st.spinner("Analyzing document with high-power AI..."):
            prompt = f"""
SYSTEM: You are a professional Public Policy Analyst. 
TASK: Analyze the Bill text below for 8th grade students. Use simple, clear language.
IMPORTANT: Do NOT generate random sequences of numbers. Use ONLY the provided text.
FORMAT: Use EXACTLY the headings below. No markdown symbols like ** or #.

SECTOR:
(One word: Agri / Finance / Education / Healthcare / Tech / Environment / Defence / Other)

OBJECTIVE:
(3 to 5 short lines explaining the purpose)

DETAILED SUMMARY:
(10 to 20 simple bullet points)

IMPACT ANALYSIS:
Citizens:
- Bullet points
Businesses:
- Bullet points
Government:
- Bullet points

BENEFICIARIES:
- Bullet points

AFFECTED GROUPS:
- Bullet points

POSITIVES:
- Bullet points

NEGATIVES / RISKS:
- Bullet points

TEXT:
{st.session_state.full_text[:18000]}
"""
            try:
                response = llm.invoke(prompt)
                st.session_state.analysis = response.content
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------- HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content: return "No data."
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

def generate_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica", 10)
    for line in text.split("\n"):
        if y < 50: pdf.showPage(); y = 800
        pdf.drawString(50, y, line[:95])
        y -= 15
    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- UI DISPLAY (RESTORED SIZES) ----------------
if st.session_state.analysis:
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["🏷️ Sector", "📄 Summary", "📊 Impact Analysis"])

    with tab1:
        st.header("🏷️ Identified Sector")
        st.info(extract("SECTOR:"))

    with tab2:
        st.header("📄 Bill Summary")
        st.subheader("🎯 Objective")
        st.write(extract("OBJECTIVE:"))
        
        st.subheader("💡 Detailed Summary")
        detail = extract("DETAILED SUMMARY:")
        st.write(detail)
        # RESTORED: PDF Downloadable Summary
        st.download_button("⬇️ Download Detailed Summary (PDF)", generate_pdf(detail), "Bill_Summary.pdf")

    with tab3:
        st.header("📊 Impact Analysis")
        # RESTORED: Large formatted boxes for impact
        st.markdown(f"### {extract('IMPACT ANALYSIS:')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.success("✅ **Positives**\n\n" + extract("POSITIVES:"))
            st.write("💎 **Beneficiaries:**", extract("BENEFICIARIES:"))
        with col2:
            st.error("⚠️ **Risks**\n\n" + extract("NEGATIVES / RISKS:"))
            st.write("👥 **Affected Groups:**", extract("AFFECTED GROUPS:"))

# ---------------- CHAT ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    user_q = st.text_input("Ask a specific question about a clause or rule:")
    if user_q:
        with st.spinner("Searching bill text..."):
            ans = llm.invoke(f"Provide a textual answer for an 8th grader. No numbers. Context: {st.session_state.full_text[:12000]}\nQuestion: {user_q}")
            st.chat_message("assistant").write(ans.content)

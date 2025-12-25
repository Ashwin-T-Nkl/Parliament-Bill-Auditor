import streamlit as st
from pypdf import PdfReader
import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from langchain_groq import ChatGroq

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Parliament Bill Auditor", layout="wide")
st.title("🏛️ Parliament Bill Auditor")

# ---------------- VALIDATION ----------------
BILL_KEYWORDS = [
    "bill", "act", "parliament", "lok sabha", "rajya sabha", "gazette", 
    "legislative", "enacted", "minister", "ministry", "objects and reasons",
    "vidheyak", "adhiniyam", "purasthapit", "introduced", "passed"
]

def is_valid_government_doc(text):
    if len(text.strip()) < 100: return False
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
            try:
                t = page.extract_text()
                if t: raw_text += t + "\n"
            except: pass
        st.session_state.full_text = raw_text

    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY.")
        st.stop()

    # POWERFUL MODEL: Using 70B with temperature 0.2 to prevent number/text looping
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile", 
        temperature=0.2, 
        max_tokens=3500
    )

    if st.button("🔍 Generate Analysis"):
        with st.spinner("Analyzing document..."):
            prompt = f"""
SYSTEM: You are a professional Policy Analyst. Do not generate random legal articles or counting sequences.
TASK: Analyze the Bill text below for 8th grade students. Use ONLY the text provided.
FORMAT: Use the headings provided. No markdown symbols like ** or #.

SECTOR:
One word: Agri, Finance, Education, Healthcare, Tech, Environment, Defence, etc.,
be presice and find the sector Correctly and answer in one word.

OBJECTIVE:
(3 to 5 short lines)

DETAILED SUMMARY:
(10 to 20 bullet points)

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

# ---------------- EXTRACTION HELPER ----------------
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
    except: return "Parsing error."

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

# ---------------- UI DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["🏷️ Sector", "📄 Summary", "📊 Impact"])

    with tab1:
        st.header("🏷️ Identified Sector")
        st.info(extract("SECTOR:"))
    with tab2:
        st.header("📄 Bill Summary")
        st.subheader("🎯 Objective")
        st.write(extract("OBJECTIVE:"))
        st.subheader("💡 Provisions")
        detail = extract("DETAILED SUMMARY:")
        st.write(detail)
        st.download_button("⬇️ Download PDF Summary", generate_pdf(detail), "Bill_Summary.pdf")
    with tab3:
        st.header("📊 Impact Analysis")
        st.write(extract("IMPACT ANALYSIS:"))
        c1, c2 = st.columns(2)
        with c1:
            st.success("✅ **Positives**\n\n" + extract("POSITIVES:"))
            st.write("**Beneficiaries:**", extract("BENEFICIARIES:"))
        with c2: # FIXED TYPO: col2 changed to c2
            st.error("⚠️ **Risks**\n\n" + extract("NEGATIVES / RISKS:"))
            st.write("**Affected Groups:**", extract("AFFECTED GROUPS:"))

# ---------------- AI CHAT (FIXED) ----------------
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    user_q = st.text_input("Ask a specific question about a clause or rule:")

    if user_q:
        with st.spinner("Searching bill text..."):
            chat_prompt = f"""
            SYSTEM: 
            You are a Public Policy Analyst helping 8th-grade students. Give simple precise answers.
            Answer the question based ONLY on the provided Parliamentary Bill text.
            If the answer is not in the text, politely inform that no answer available.
            If it is in other Language, skip and read English only.
            Keep the tone simple, professional, and educational.
            Do not display other language content. if you cannot find answer state the relevant info if needed or simply that no answer available.

            BILL CONTEXT:
            {st.session_state.full_text[:15000]}

            QUESTION:
            {user_q}

            ANSWER:
            """
            ans = llm.invoke(chat_prompt)
            st.chat_message("assistant").write(ans.content)


import streamlit as st
from pypdf import PdfReader
import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Parliament Bill Auditor", layout="wide")
st.title("🏛️ Parliament Bill Auditor")

# ---------------- SESSION STATE ----------------
for key in ["analysis", "view", "last_file", "full_text"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "full_text" else ""

# ---------------- UTILITIES ----------------
def clean_text(text):
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*", "", text)
    return text.strip()

def extract_section(title, text):
    pattern = rf"{title}\s*(.*?)(?:\n[A-Z /()]+?:|\Z)"
    match = re.search(pattern, text, re.S)
    return clean_text(match.group(1)) if match else "Not available"

def is_government_bill(text):
    indicators = [
        "bill", "be it enacted", "statement of objects",
        "arrangement of clauses", "this act may be called",
        "lok sabha", "rajya sabha", "gazette of india",
        "ministry of law", "financial memorandum", "commencement"
    ]
    score = sum(1 for k in indicators if k in text.lower())
    return score >= 3

def create_pdf(text):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            c.showPage()
            y = 800
        c.drawString(40, y, line[:110])
        y -= 14
    c.save()
    buffer.seek(0)
    return buffer

# ---------------- UPLOAD ----------------
uploaded_file = st.file_uploader(
    "Upload Government / Parliamentary Bill PDF",
    type=["pdf"]
)

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.view = None
        st.session_state.full_text = ""

    reader = PdfReader(uploaded_file)
    full_text = ""

    for page in reader.pages:
        try:
            txt = page.extract_text()
            if txt:
                full_text += txt + "\n"
        except:
            pass

    st.session_state.full_text = full_text

    # ---------------- ANALYSIS ----------------
    if st.button("🔍 Generate Analysis"):
        if not is_government_bill(full_text[:20000]):
            st.warning("📄 Kindly upload a valid Government / Parliamentary Bill PDF.")
            st.stop()

        if "GROQ_API_KEY" not in os.environ:
            st.error("❌ GROQ_API_KEY not configured in Streamlit Cloud.")
            st.stop()

        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )

        prompt = f"""
You are a Public Policy Analyst.

Your audience:
• 8th grade school students
• Common citizens with no legal background

Analyze ONLY the given bill text.
Do NOT assume anything outside the bill.

Return EXACTLY these headings (no markdown):

SECTOR:
OBJECTIVE:
SUMMARY (SIMPLE):
SUMMARY (DETAILED):
IMPACT ANALYSIS:
BENEFICIARIES:
AFFECTED GROUPS:
POSITIVES:
NEGATIVES / RISKS:

Rules:
• Sector must be ONE word
• Simple language
• Clear bullet points
• Use ONLY bill text

BILL TEXT:
{full_text[:12000]}
"""

        with st.spinner("Analyzing bill..."):
            st.session_state.analysis = llm.invoke(prompt).content
            st.session_state.view = None

# ---------------- NAVIGATION ----------------
if st.session_state.analysis:
    st.markdown("### 📌 Explore Analysis")
    c1, c2, c3, c4 = st.columns(4)

    if c1.button("🏷️ Sector"):
        st.session_state.view = "sector"
    if c2.button("📄 Simple Summary"):
        st.session_state.view = "simple"
    if c3.button("📘 Detailed Summary"):
        st.session_state.view = "detailed"
    if c4.button("📊 Impact"):
        st.session_state.view = "impact"

st.markdown("---")

# ---------------- VIEWS ----------------
if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.write(extract_section("SECTOR:", st.session_state.analysis))

elif st.session_state.view == "simple":
    st.header("📄 Simple Summary")
    st.write(extract_section("SUMMARY (SIMPLE):", st.session_state.analysis))

elif st.session_state.view == "detailed":
    st.header("📘 Detailed Summary")
    detail = extract_section("SUMMARY (DETAILED):", st.session_state.analysis)
    st.write(detail)
    st.download_button(
        "⬇️ Download Summary as PDF",
        create_pdf(detail),
        "Bill_Detailed_Summary.pdf"
    )

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")
    st.write(extract_section("IMPACT ANALYSIS:", st.session_state.analysis))

# ---------------- Q&A ----------------
if st.session_state.analysis:
    st.markdown("---")
    q = st.text_input("Ask a question about this bill")
    if q:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
        answer = llm.invoke(f"""
Answer ONLY from the bill text.

BILL TEXT:
{st.session_state.full_text[:12000]}

QUESTION:
{q}
""")
        st.write(clean_text(answer.content))

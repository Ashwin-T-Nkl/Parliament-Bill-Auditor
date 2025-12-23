import streamlit as st
from pypdf import PdfReader
import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader(" ", type=["pdf"])

if uploaded_file:
    # Reset state on new file
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.view = None
        st.session_state.full_text = ""

    reader = PdfReader(uploaded_file)
    full_text = ""

    for page in reader.pages:
        try:
            text = page.extract_text()
            if text:
                full_text += text
        except:
            continue

    st.session_state.full_text = full_text

    # ---------------- GENERATE ANALYSIS ----------------
    if st.button("🔍 Generate Analysis"):
        text = full_text[:12000].lower()

        # -------- MERGED LEGISLATIVE / OFFICIAL MARKERS --------
        bill_markers = [
            "be it enacted by parliament",
            "it is hereby enacted",
            "this act may be called",
            "shall come into force",
            "notwithstanding anything contained",
            "may, by notification",
            "lok sabha",
            "rajya sabha",
            "gazette of india",
            "as introduced in lok sabha",
            "as introduced in rajya sabha",
            "statement of objects and reasons",
            "short title and commencement",
            "arrangement of clauses",
            "financial memorandum",
            "memorandum regarding delegated legislation",
            "president's recommendation",
            "president's recommendation",
            "government of india press",
            "bill no."
        ]

        match_count = sum(1 for marker in bill_markers if marker in text)

        # Require multiple legislative signals
        is_bill = match_count >= 3

        if not is_bill:
            st.warning("📄 Kindly upload an official Government / Parliamentary Bill PDF.")
            st.stop()

        # -------- GROQ LLM --------
        if "GROQ_API_KEY" not in os.environ:
            st.error("AI service is not configured.")
            st.stop()

        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

        with st.spinner("Analyzing bill..."):
            prompt = f"""
You are a Public Policy Analyst.

Your readers are 8th Grade School students and common citizens.

Return clearly labeled sections using simple language.

SECTOR:
One word primary sector.

OBJECTIVE:
Explain the main objective of this bill in 3–4 simple lines.

SUMMARY (DETAILED):
10–15 bullet points explaining:
- What the bill does
- Why it matters
- What changes for a normal person

IMPACT ANALYSIS:
Citizens:
Businesses:
Government:
Industries / Markets:
NGOs / Civil Society:

BENEFICIARIES:
Which sectors benefit or gain opportunities.

AFFECTED GROUPS:
Which sectors face restrictions or costs.

POSITIVES:
NEGATIVES / RISKS:

Use only the bill text.

BILL TEXT:
{full_text[:12000]}
"""
            response = llm.invoke(prompt)
            st.session_state.analysis = response.content
            st.session_state.view = None

# ---------------- TILE NAVIGATION ----------------
if st.session_state.analysis:
    st.markdown("### 📌 Explore Analysis")
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("🏷️ Sector"):
            st.session_state.view = "sector"
    with c2:
        if st.button("📄 Summary"):
            st.session_state.view = "summary"
    with c3:
        if st.button("📊 Impact"):
            st.session_state.view = "impact"

# ---------------- HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content or title not in content:
        return "Not available"
    return content.split(title)[1].split("\n\n")[0].replace("**", "").strip()

def generate_summary_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica", 10)

    for line in text.split("\n"):
        if y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = 800
        pdf.drawString(40, y, line[:100])
        y -= 14

    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- CONTENT ----------------
st.markdown("---")

if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.markdown(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Bill Summary")
    st.subheader("🎯 Objective")
    st.markdown(extract("OBJECTIVE:"))

    if st.button("📘 View Detailed Summary"):
        detailed = extract("SUMMARY (DETAILED):")
        st.markdown(detailed)
        st.download_button(
            "⬇️ Download Summary PDF",
            generate_summary_pdf(detailed),
            "Bill_Summary.pdf",
            "application/pdf"
        )

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")
    st.markdown(extract("IMPACT ANALYSIS:"))
    st.subheader("Beneficiaries")
    st.markdown(extract("BENEFICIARIES:"))
    st.subheader("Affected Groups")
    st.markdown(extract("AFFECTED GROUPS:"))
    st.subheader("Positives")
    st.markdown(extract("POSITIVES:"))
    st.subheader("Risks")
    st.markdown(extract("NEGATIVES / RISKS:"))

# ---------------- AI CHAT ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")

    question = st.text_input("Ask a question")

    if question:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

        answer = llm.invoke(f"""
Answer ONLY using the bill text below.
If not found, clearly say so.

BILL TEXT:
{st.session_state.full_text[:12000]}

QUESTION:
{question}
""")
        st.write(answer.content)

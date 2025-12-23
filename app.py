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
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

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
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        except:
            pass

    st.session_state.full_text = full_text

    if "GROQ_API_KEY" not in os.environ:
        st.error("AI service not configured.")
        st.stop()

    llm = ChatGroq(
        model_name="llama-3.1-8b-instant",
        temperature=0
    )

    if st.button("🔍 Generate Analysis"):
        with st.spinner("Analyzing bill..."):
            prompt = f"""
You are a Public Policy Analyst.

Your readers are 8th Grade School students and common citizens.

Return clearly labeled sections using simple language.

SECTOR:
One word primary sector.

OBJECTIVE:
Explain the main objective of this bill in 3–4 simple lines. Bullet Points

SUMMARY (DETAILED):
Provide a 10–20 bullet point explanation. Bullet Points

IMPACT ANALYSIS: Bullet Points
Citizens:
Businesses:
Government:
Industries / Markets:
NGOs / Civil Society:

BENEFICIARIES: Bullet Points
AFFECTED GROUPS:
POSITIVES:
NEGATIVES / RISKS:

Rules:
- Use only the bill text
- Do not assume facts
- Keep language simple
Bullet Points

BILL TEXT:
{st.session_state.full_text[:20000]}
"""
            response = llm.invoke(prompt)
            st.session_state.analysis = response.content
            st.session_state.view = None

# ---------------- NAVIGATION ----------------
if st.session_state.analysis:
    st.markdown("### 📌 Explore Analysis")
    c1, c2, c3 = st.columns(3)

    if c1.button("🏷️ Sector"):
        st.session_state.view = "sector"
    if c2.button("📄 Summary"):
        st.session_state.view = "summary"
    if c3.button("📊 Impact"):
        st.session_state.view = "impact"

# ---------------- DISPLAY CLEANER ----------------
def extract(title):
    content = st.session_state.analysis
    if not content or title not in content:
        return "Not available"

    text = content.split(title)[1].split("\n\n")[0]

    # CLEAN MARKDOWN JUNK (DISPLAY ONLY)
    for m in ["**", "__", "##", "###", "*"]:
        text = text.replace(m, "")

    return text.strip()

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

# ---------------- CONTENT ----------------
st.markdown("---")

if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.write(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Bill Summary")
    st.subheader("🎯 Objective")
    st.write(extract("OBJECTIVE:"))

    if st.button("📘 View Detailed Summary"):
        detail = extract("SUMMARY (DETAILED):")
        st.write(detail)
        st.download_button(
            "⬇️ Download Detailed Summary (PDF)",
            generate_summary_pdf(detail),
            "Bill_Detailed_Summary.pdf",
            "application/pdf"
        )

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")

    st.subheader("Impact")
    st.write(extract("IMPACT ANALYSIS:"))

    st.subheader("Beneficiaries")
    st.write(extract("BENEFICIARIES:"))

    st.subheader("Affected Groups")
    st.write(extract("AFFECTED GROUPS:"))

    st.subheader("Positives")
    st.write(extract("POSITIVES:"))

    st.subheader("Risks")
    st.write(extract("NEGATIVES / RISKS:"))

# ---------------- AI CHAT (UNCHANGED) ----------------
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")

    user_q = st.text_input("Ask a question")

    if user_q:
        with st.spinner("Thinking..."):
            chat_prompt = f"""
Answer the question based on the Parliamentary Bill text below.

BILL TEXT:
{st.session_state.full_text[:20000]}

QUESTION:
{user_q}
"""
            answer = llm.invoke(chat_prompt)
            st.write(answer.content)

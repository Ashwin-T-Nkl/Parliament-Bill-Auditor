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
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "view" not in st.session_state:
    st.session_state.view = None
if "last_file" not in st.session_state:
    st.session_state.last_file = None
if "full_text" not in st.session_state:
    st.session_state.full_text = ""

# ---------------- SIMPLE BILL VALIDATION ----------------
bill_keywords = [
    "bill",
    "act",
    "speaker",
    "parliament",
    "parliament of india",
    "lok sabha",
    "loksabha",
    "rajya sabha",
    "rajyasabha",
    "government of india",
    "gazette",
    "legislative",
    "statement of objects",
    "statement of objects and reasons",
    "extent",
    "commencement",
    "enacted",
    "ministry of law"
]

def is_government_bill(text):
    text = text.lower()
    return any(k in text for k in bill_keywords)

# ---------------- PDF CREATOR ----------------
def create_pdf(text):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            c.showPage()
            y = 800
        c.drawString(40, y, line[:100])
        y -= 14
    c.save()
    buf.seek(0)
    return buf

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader(
    "Upload Government / Parliamentary Bill PDF",
    type=["pdf"]
)

if uploaded_file:
    # reset state on new file
    if uploaded_file.name != st.session_state.last_file:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.view = None
        st.session_state.full_text = ""

    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        try:
            t = page.extract_text()
            if t:
                text += t + "\n"
        except:
            pass

    st.session_state.full_text = text

    if not is_government_bill(text):
        st.error("❌ Kindly upload a valid Government / Parliamentary Bill PDF.")
        st.stop()

    # ---------------- ANALYSIS ----------------
    if st.button("🔍 Generate Analysis"):
        if "GROQ_API_KEY" not in os.environ:
            st.error("AI service not configured.")
            st.stop()

        llm = ChatGroq(
            model_name="llama-3.1-8b-instant",  # IMPORTANT
            temperature=0
        )

        prompt = f"""
You are a Public Policy Analyst.

Audience: 8th grade students and common citizens.
Use very simple language.

Return EXACTLY the following headings and follow the rules strictly.

SECTOR:
- ONE word only

OBJECTIVE:
- 3 to 5 short lines

SIMPLE SUMMARY:
- 3 to 5 short lines
- Each line must be separate
- Do NOT write a paragraph

DETAILED SUMMARY:
- 10 to 20 bullet points
- Each bullet must start with a dash (-)

IMPACT ANALYSIS:
Citizens:
- Bullet points
Businesses:
- Bullet points
Government:
- Bullet points
Industries / Markets:
- Bullet points
NGOs / Civil Society:
- Bullet points

BENEFICIARIES:
- Bullet points

AFFECTED GROUPS:
- Bullet points

POSITIVES:
- Bullet points

NEGATIVES / RISKS:
- Bullet points

Rules:
- Use ONLY the bill text
- No assumptions
- No markdown symbols like ** or ###

BILL TEXT:
{text[:6000]}
"""

        with st.spinner("Analyzing bill..."):
            st.session_state.analysis = llm.invoke(prompt).content
            st.session_state.view = None

# ---------------- NAVIGATION ----------------
if st.session_state.analysis:
    c1, c2, c3 = st.columns(3)
    if c1.button("🏷️ Sector"):
        st.session_state.view = "sector"
    if c2.button("📄 Summary"):
        st.session_state.view = "summary"
    if c3.button("📊 Impact"):
        st.session_state.view = "impact"

# ---------------- EXTRACT ----------------
def extract(title):
    try:
        return st.session_state.analysis.split(title)[1].split("\n\n")[0].strip()
    except:
        return "Not available"

# ---------------- DISPLAY ----------------
st.markdown("---")

if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.write(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Bill Summary")

    st.subheader("🎯 Objective")
    st.write(extract("OBJECTIVE:"))

    st.subheader("📝 Simple Summary")
    st.write(extract("SIMPLE SUMMARY:"))

    if st.button("📘 View Detailed Summary"):
        detail = extract("DETAILED SUMMARY:")
        st.write(detail)

        st.download_button(
            "⬇️ Download Detailed Summary PDF",
            create_pdf(detail),
            "Detailed_Bill_Summary.pdf",
            "application/pdf"
        )

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")
    st.write(extract("IMPACT ANALYSIS:"))

    st.subheader("Beneficiaries")
    st.write(extract("BENEFICIARIES:"))

    st.subheader("Affected Groups")
    st.write(extract("AFFECTED GROUPS:"))

    st.subheader("Positives")
    st.write(extract("POSITIVES:"))

    st.subheader("Risks")
    st.write(extract("NEGATIVES / RISKS:"))

# ---------------- SIMPLE AI CHAT ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.header("💬 Ask about this Bill")

    q = st.text_input("Ask a question")
    if q:
        llm = ChatGroq(
            model_name="llama-3.1-8b-instant",
            temperature=0
        )

        chat_prompt = f"""
Answer ONLY using the analysis below.
Keep the answer simple.

ANALYSIS:
{st.session_state.analysis}

QUESTION:
{q}
"""
        st.write(llm.invoke(chat_prompt).content)

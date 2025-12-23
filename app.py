import streamlit as st
from pypdf import PdfReader
import os
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

# ---------------- SIMPLE KEYWORD VALIDATION ----------------
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

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader(
    "Upload Government / Parliamentary Bill PDF",
    type=["pdf"]
)

if uploaded_file:
    # reset on new file
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
            model_name="llama-3.1-8b-instant",
            temperature=0
        )

        prompt = f"""
You are a Public Policy Analyst.

Audience: 8th grade students and common citizens.
Use very simple language.

Return EXACTLY these headings:

SECTOR:
(One word)

OBJECTIVE:
(3–5 simple lines)

SUMMARY:
(10–20 bullet points)

IMPACT ANALYSIS:
Citizens:
Businesses:
Government:
Industries / Markets:
NGOs / Civil Society:

BENEFICIARIES:
(Bullet points)

AFFECTED GROUPS:
(Bullet points)

POSITIVES:
(Bullet points)

NEGATIVES / RISKS:
(Bullet points)

Rules:
- Use only the bill text
- No assumptions
- No markdown symbols

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
        return st.session_state.analysis.split(title)[1].split("\n\n")[0]
    except:
        return "Not available"

# ---------------- DISPLAY ----------------
st.markdown("---")

if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.write(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Summary")
    st.write(extract("SUMMARY:"))

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

# ---------------- SIMPLE CHAT ----------------
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

ANALYSIS:
{st.session_state.analysis}

QUESTION:
{q}
"""
        st.write(llm.invoke(chat_prompt).content)

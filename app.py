import streamlit as st
from pypdf import PdfReader
import os

st.set_page_config(
    page_title="Parliament Bill Auditor",
    layout="wide"
)

st.title("🏛️ Parliament Bill Auditor")

# ---------------- SESSION STATE ----------------
if "view" not in st.session_state:
    st.session_state.view = None

if "analysis" not in st.session_state:
    st.session_state.analysis = None

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    reader = PdfReader(uploaded_file)
    full_text = ""

    for page in reader.pages:
        try:
            text = page.extract_text()
            if text:
                full_text += text
        except:
            continue

    if "GROQ_API_KEY" in os.environ:
        from langchain_groq import ChatGroq

        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )

        if st.button("🔍 Generate Analysis"):
            with st.spinner("Analyzing bill..."):
                prompt = f"""
You are a Public Policy Analyst.

Your readers are 8th Grade School Kid.

Return clearly labeled sections:

SECTOR: One Word, Which Sector it belongs to.
SUMMARY: simple summary in less than 10 lines in Bullet Points
IMPACT:
- Short-term, Bullet Points
- Medium-term, Bullet Points
- Long-term, Bullet Points

BENEFICIARIES: Bullet Points, less than 5  points
AFFECTED GROUPS: Bullet Points, less than 5  points
POSITIVES: Bullet Points, less than 10  points
NEGATIVES: Bullet Points, less than 10  points

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

# ---------------- FULL PAGE CONTENT ----------------
def extract(title):
    content = st.session_state.analysis
    if title not in content:
        return "Not available"
    return content.split(title)[1].split("\n\n")[0].strip()

st.markdown("---")

if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.write(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Bill Summary")
    st.write(extract("SUMMARY:"))

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")
    st.subheader("Impact Timeline")
    st.write(extract("IMPACT:"))

    st.subheader("Beneficiaries")
    st.write(extract("BENEFICIARIES:"))

    st.subheader("Affected Groups")
    st.write(extract("AFFECTED GROUPS:"))

    st.subheader("Positives")
    st.write(extract("POSITIVES:"))

    st.subheader("Risks")
    st.write(extract("NEGATIVES:"))

# ---------------- AI CHAT ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")

    user_q = st.text_input("Ask a question")

    if user_q:
        with st.spinner("Thinking..."):
            chat_prompt = f"""
Answer the question using ONLY the bill analysis below.

BILL ANALYSIS:
{st.session_state.analysis}

QUESTION:
{user_q}
"""
            answer = llm.invoke(chat_prompt)
            st.write(answer.content)


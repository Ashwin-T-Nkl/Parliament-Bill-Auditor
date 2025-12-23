
import streamlit as st
from pypdf import PdfReader
import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

st.set_page_config(page_title="Parliament Bill Auditor", layout="wide")
st.title("🏛️ Parliament Bill Auditor")

# ---------- Session ----------
for key in ["analysis", "view", "last_file", "full_text"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "full_text" else ""

# ---------- Upload ----------
uploaded_file = st.file_uploader("Upload Government / Parliamentary Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.view = None
        st.session_state.full_text = ""

    reader = PdfReader(uploaded_file)
    text = ""

    for page in reader.pages:
        try:
            page_text = page.extract_text()
            if page_text:
                text += page_text
        except:
            pass

    st.session_state.full_text = text

    # ---------- Generate ----------
    if st.button("🔍 Generate Analysis"):
        preview = text[:15000].lower()

        bill_indicators = [
            "bill",
            "short title",
            "statement of objects",
            "statement of objects and reasons",
            "arrangement of clauses",
            "be it enacted",
            "this act may be called",
            "lok sabha",
            "rajya sabha",
            "gazette of india",
            "ministry of law",
            "financial memorandum",
            "commencement",
        ]

        is_bill = any(indicator in preview for indicator in bill_indicators)

        if not is_bill:
            st.warning("📄 Kindly upload a Government / Parliamentary Bill PDF.")
            st.stop()

        if "GROQ_API_KEY" not in os.environ:
            st.error("AI service not configured.")
            st.stop()

        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

        with st.spinner("Analyzing bill..."):
            prompt = f"""
                You are a Public Policy Analyst.

                Your readers are 8th Grade School students and common citizens.

                Return clearly labeled sections using simple language.
 
                SECTOR:
                One word primary sector (e.g., Finance, Agriculture, Transport, Energy, Shipping).
                    
                OBJECTIVE:
                Explain the main objective of this bill in 3–4 simple lines.
                    
                SUMMARY (DETAILED):
                Provide a 10–20 bullet point explanation:
                    - What the bill does
                    - Why it matters
                    - What changes for a normal person
                    
                IMPACT ANALYSIS:
                Explain the impact separately for each group:
                    
                Citizens:
                (Bullet points)
                    
                Businesses:
                (Bullet points)
                    
                Government:
                (Bullet points)
                    
                Industries / Markets:
                (Bullet points)
                    
                NGOs / Civil Society:
                (Bullet points)
                    
                BENEFICIARIES:
                Clearly mention:
                    - Which sectors benefit
                    - Which sectors get new business or growth opportunities
                    
                AFFECTED GROUPS:
                Clearly mention:
                    - Which sectors face restrictions
                    - Which sectors face higher costs, compliance, or limitations
                    
                POSITIVES:
                (Bullet points focusing on advantages and opportunities)
                    
                NEGATIVES / RISKS:
                (Bullet points focusing on risks, costs, resistance, or implementation challenges)
                    
                Rules:
                    - Use only the bill text
                    - Do not assume facts
                    - Keep language simple

                Use only the bill text.
BILL TEXT:
{text[:12000]}
"""
            st.session_state.analysis = llm.invoke(prompt).content
            st.session_state.view = None

# ---------- Navigation ----------
if st.session_state.analysis:
    st.markdown("### 📌 Explore Analysis")
    c1, c2, c3 = st.columns(3)

    if c1.button("🏷️ Sector"):
        st.session_state.view = "sector"
    if c2.button("📄 Summary"):
        st.session_state.view = "summary"
    if c3.button("📊 Impact"):
        st.session_state.view = "impact"

def extract(title):
    try:
        return st.session_state.analysis.split(title)[1].split("\n\n")[0]
    except:
        return "Not available"

def pdf(text):
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

st.markdown("---")

if st.session_state.view == "sector":
    st.header("Sector")
    st.write(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("Summary")
    st.write(extract("OBJECTIVE:"))

    if st.button("View Detailed Summary"):
        detail = extract("SUMMARY")
        st.write(detail)
        st.download_button("Download PDF", pdf(detail), "Bill_Summary.pdf")

elif st.session_state.view == "impact":
    st.header("Impact")
    st.write(extract("IMPACT"))

# ---------- Chat ----------
if st.session_state.analysis:
    st.markdown("---")
    q = st.text_input("Ask about this bill")
    if q:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
        ans = llm.invoke(f"""
Answer ONLY from the bill text.

BILL TEXT:
{st.session_state.full_text[:12000]}

QUESTION:
{q}
""")
        st.write(ans.content)






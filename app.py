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
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

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
        # ---- BILL VALIDATION (HERE is the fix) ----
        preview_text = full_text[:4000].lower()

        bill_keywords = [
            "bill",
            "act",
            "parliament",
            "parliament of india",
            "lok sabha",
            "rajya sabha",
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

        is_bill = any(k in preview_text for k in bill_keywords)

        if not is_bill:
            st.warning("📄 Kindly upload a Parliamentary Bill–related PDF.")
            st.stop()

        # ---- GROQ ANALYSIS ONLY IF VALID ----
        if "GROQ_API_KEY" not in os.environ:
            st.error("AI service not configured.")
            st.stop()

        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )

        with st.spinner("Analyzing bill..."):
            prompt = f"""
You are a Public Policy Analyst.

Your readers are 8th Grade School students and common citizens.

Return clearly labeled sections using simple language.

SECTOR:
One word primary sector.

OBJECTIVE:
Explain the main objective in 3–4 lines.

SUMMARY (DETAILED):
10–20 bullet points explaining the bill.

IMPACT ANALYSIS:
Citizens:
Businesses:
Government:
Industries / Markets:
NGOs / Civil Society:

BENEFICIARIES:
Sectors that benefit or gain opportunities.

AFFECTED GROUPS:
Sectors facing restrictions or costs.

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
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
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
    buf.seek(0)
    return buf

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
        detail = extract("SUMMARY (DETAILED):")
        st.markdown(detail)
        st.download_button(
            "⬇️ Download Summary PDF",
            generate_summary_pdf(detail),
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

# ---------------- CHAT ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    q = st.text_input("Ask a question")
    if q:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
        ans = llm.invoke(f"""
Answer ONLY from the bill text below.

BILL TEXT:
{st.session_state.full_text[:12000]}

QUESTION:
{q}
""")
        st.write(ans.content)

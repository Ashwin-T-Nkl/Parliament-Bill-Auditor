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
if "view" not in st.session_state:
    st.session_state.view = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "last_file" not in st.session_state:
    st.session_state.last_file = None
if "full_text" not in st.session_state:
    st.session_state.full_text = ""

# ---------------- STRICT BILL VALIDATION ----------------
def is_government_bill(text):
    if not text or len(text.strip()) < 1200:
        return False

    text = text.lower()

    bill_identity = [
        r"\bintroduction of the .* bill\b",
        r"\bthe .* bill\b",
        r"\b.* bill, \d{4}\b"
    ]

    parliament_context = [
        r"lok sabha",
        r"rajya sabha",
        r"hon\. speaker",
        r"hon\. chairperson",
        r"parliament of india"
    ]

    bill_action = [
        r"leave to introduce a bill",
        r"i introduce the bill",
        r"motion moved",
        r"the motion was adopted",
        r"i rise to oppose .* bill",
        r"be it enacted"
    ]

    return (
        any(re.search(p, text) for p in bill_identity)
        and any(re.search(p, text) for p in parliament_context)
        and any(re.search(p, text) for p in bill_action)
    )

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Government / Parliamentary Bill PDF", type=["pdf"])

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
            t = page.extract_text()
            if t:
                full_text += t + "\n"
        except:
            pass

    st.session_state.full_text = full_text

    # -------- STRICT VALIDATION --------
    if not is_government_bill(full_text):
        st.error(
            "❌ Invalid document.\n\n"
            "Only Government / Parliamentary Bill PDFs "
            "(Introduction, Debate, or Bill text from Sansad) are allowed."
        )
        st.stop()

    # ---------------- ANALYSIS ----------------
    if st.button("🔍 Generate Analysis"):
        if "GROQ_API_KEY" not in os.environ:
            st.error("AI service not configured.")
            st.stop()

        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

        # 🔒 DETAILED PROMPT (UNCHANGED IN SPIRIT)
        prompt = f"""
You are a Public Policy Analyst.

Your audience:
• 8th grade school students
• Common citizens with no legal background

Analyze ONLY the given bill text.
Do NOT assume anything outside the bill.

------------------------------------
SECTOR:
------------------------------------
• ONE word sector only

------------------------------------
OBJECTIVE:
------------------------------------
• 3–5 simple lines

------------------------------------
SUMMARY (DETAILED):
------------------------------------
• 10–20 bullet points
• One idea per bullet

------------------------------------
IMPACT ANALYSIS:
------------------------------------
Citizens:
Businesses:
Government:
Industries / Markets:
NGOs / Civil Society:

------------------------------------
BENEFICIARIES:
------------------------------------
• Bullet points

------------------------------------
AFFECTED GROUPS:
------------------------------------
• Bullet points

------------------------------------
POSITIVES:
------------------------------------
• Bullet points

------------------------------------
NEGATIVES / RISKS:
------------------------------------
• Bullet points

------------------------------------
RULES:
------------------------------------
• Use ONLY bill text
• Simple language
• No markdown

------------------------------------
BILL TEXT:
{full_text[:12000]}
"""
        with st.spinner("Analyzing bill..."):
            st.session_state.analysis = llm.invoke(prompt).content
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

# ---------------- HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content or title not in content:
        return "Not available"
    return content.split(title)[1].split("\n\n")[0].strip()

def generate_pdf(text):
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

# ---------------- DISPLAY ----------------
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
            generate_pdf(detail),
            "Bill_Summary.pdf",
            "application/pdf"
        )

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")
    st.subheader("Citizens")
    st.markdown(extract("Citizens:"))
    st.subheader("Businesses")
    st.markdown(extract("Businesses:"))
    st.subheader("Government")
    st.markdown(extract("Government:"))
    st.subheader("Industries / Markets")
    st.markdown(extract("Industries / Markets:"))
    st.subheader("NGOs / Civil Society")
    st.markdown(extract("NGOs / Civil Society:"))

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
    q = st.text_input("Ask a question")
    if q:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
        ans = llm.invoke(f"""
Answer ONLY using the bill text.

BILL TEXT:
{st.session_state.full_text[:12000]}

QUESTION:
{q}
""")
        st.write(ans.content)

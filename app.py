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
    st.session_state.analysis = ""
if "last_file" not in st.session_state:
    st.session_state.last_file = None
if "full_text" not in st.session_state:
    st.session_state.full_text = ""

# ---------------- NLP: KEEP ENGLISH ONLY ----------------
def keep_english_text(text):
    lines = text.splitlines()
    english_lines = []
    for line in lines:
        if not re.search(r'[\u0900-\u097F]', line):  # Hindi Unicode range
            english_lines.append(line)
    return "\n".join(english_lines)

# ---------------- UNIVERSAL BILL VALIDATION ----------------
def is_government_bill(text):
    if not text or len(text.strip()) < 1000:
        return False

    text = text.lower().replace(" ", "")

    has_bill = "bill" in text
    has_parliament = any(k in text for k in ["loksabha", "rajyasabha", "parliamentofindia"])
    has_action = any(
        k in text for k in [
            "introduce",
            "introduction",
            "motion",
            "debate",
            "consideration",
            "enact"
        ]
    )

    return has_bill and has_parliament and has_action

# ---------------- PDF GENERATOR ----------------
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

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader(
    "Upload Government / Parliamentary Bill PDF",
    type=["pdf"]
)

if uploaded_file:
    # HARD RESET on new upload
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = ""
        st.session_state.view = None
        st.session_state.full_text = ""

    reader = PdfReader(uploaded_file)
    raw_text = ""

    for page in reader.pages:
        try:
            t = page.extract_text()
            if t:
                raw_text += t + "\n"
        except:
            pass

    # NLP clean (drop Hindi)
    clean_text = keep_english_text(raw_text)
    st.session_state.full_text = clean_text

    # -------- STRICT UNIVERSAL VALIDATION --------
    if not is_government_bill(clean_text):
        st.error(
            "❌ Invalid document.\n\n"
            "Only Government / Parliamentary Bill PDFs "
            "from Sansad (introduction, debate, or bill text) are allowed."
        )
        st.stop()

    # ---------------- ANALYSIS ----------------
    if st.button("🔍 Generate Analysis"):
        if not st.session_state.analysis:
            if "GROQ_API_KEY" not in os.environ:
                st.error("AI service not configured.")
                st.stop()

            from langchain_groq import ChatGroq
            llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

            prompt = f"""
You are a Public Policy Analyst.

Audience:
• 8th grade students
• Common citizens

Analyze ONLY the bill text below.
Do NOT assume anything outside the bill.

------------------------------------
SECTOR:
------------------------------------
• ONE word only

------------------------------------
OBJECTIVE:
------------------------------------
• 3–5 simple bullet points

------------------------------------
SUMMARY (DETAILED):
------------------------------------
• 10–20 bullet points
• One idea per bullet

------------------------------------
IMPACT ANALYSIS:
------------------------------------
Citizens: Bullet points
Businesses: Bullet points
Government: Bullet points
Industries / Markets: Bullet points
NGOs / Civil Society: Bullet points

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
{clean_text[:7000]}
"""
            with st.spinner("Analyzing bill..."):
                try:
                    st.session_state.analysis = llm.invoke(prompt).content
                    st.session_state.view = None
                except Exception:
                    st.error(
                        "⚠️ AI service is busy.\n"
                        "Please wait a few seconds and try again."
                    )
                    st.stop()

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

def render_bullets(text):
    if not text or text == "Not available":
        st.write("Not available")
        return
    parts = [p.strip() for p in re.split(r"[.\n]", text) if p.strip()]
    for p in parts:
        st.write("•", p)

# ---------------- DISPLAY ----------------
st.markdown("---")

if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.write(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Bill Summary")
    st.subheader("🎯 Objective")
    render_bullets(extract("OBJECTIVE:"))

    if st.button("📘 View Detailed Summary"):
        detail = extract("SUMMARY (DETAILED):")
        render_bullets(detail)
        st.download_button(
            "⬇️ Download Summary PDF",
            generate_pdf(detail),
            "Bill_Summary.pdf",
            "application/pdf"
        )

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")
    st.subheader("Citizens")
    render_bullets(extract("Citizens:"))
    st.subheader("Businesses")
    render_bullets(extract("Businesses:"))
    st.subheader("Government")
    render_bullets(extract("Government:"))
    st.subheader("Industries / Markets")
    render_bullets(extract("Industries / Markets:"))
    st.subheader("NGOs / Civil Society")
    render_bullets(extract("NGOs / Civil Society:"))

    st.subheader("Beneficiaries")
    render_bullets(extract("BENEFICIARIES:"))
    st.subheader("Affected Groups")
    render_bullets(extract("AFFECTED GROUPS:"))
    st.subheader("Positives")
    render_bullets(extract("POSITIVES:"))
    st.subheader("Risks")
    render_bullets(extract("NEGATIVES / RISKS:"))

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
{st.session_state.full_text[:7000]}

QUESTION:
{q}
""")
        st.write(ans.content)

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

# ---------------- STRICT BILL VALIDATION ----------------
def is_government_bill(text):
    if not text or len(text.strip()) < 1200:
        return False

    text = text.lower()

    # 1. Bill identity (must mention a Bill)
    bill_identity = [
        r"\bthe .* bill\b",
        r"\bintroduction of the .* bill\b",
        r"\b.* bill, \d{4}\b"
    ]

    # 2. Parliamentary context
    parliament_context = [
        r"lok sabha",
        r"rajya sabha",
        r"hon\. speaker",
        r"hon\. chairperson",
        r"rules of procedure"
    ]

    # 3. Bill lifecycle action
    bill_action = [
        r"leave to introduce a bill",
        r"i introduce the bill",
        r"motion moved",
        r"the motion was adopted",
        r"i rise to oppose .* bill",
        r"clause \d+",
        r"be it enacted"
    ]

    has_identity = any(re.search(p, text) for p in bill_identity)
    has_context = any(re.search(p, text) for p in parliament_context)
    has_action = any(re.search(p, text) for p in bill_action)

    return has_identity and has_context and has_action

# ---------------- PDF CREATOR ----------------
def create_pdf(text):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in text.split("\n"):
        if y < 40:
            c.showPage()
            y = 800
        c.drawString(40, y, line[:110])
        y -= 14
    c.save()
    buf.seek(0)
    return buf

# ---------------- UPLOAD ----------------
uploaded_file = st.file_uploader(
    "Upload Government / Parliamentary Bill PDF (Sansad)",
    type=["pdf"]
)

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
            t = page.extract_text()
            if t:
                text += t + "\n"
        except:
            pass

    st.session_state.full_text = text

    # -------- STRICT VALIDATION --------
    if not is_government_bill(text):
        st.error(
            "❌ Invalid document.\n\n"
            "Only Government / Parliamentary Bill documents "
            "(Introduction, Debate, or Bill Text from Sansad) are allowed."
        )
        st.stop()

    # ---------------- ANALYSIS ----------------
    if st.button("🔍 Generate Analysis"):
        if "GROQ_API_KEY" not in os.environ:
            st.error("❌ GROQ_API_KEY not configured.")
            st.stop()

        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

        # 🔒 DO NOT MODIFY THIS PROMPT
        prompt = f"""
You

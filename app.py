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
    if not text or len(text.strip()) < 2000:
        return False

    text = text.lower()

    structural_patterns = [
        r"\ba bill to\b",
        r"\bbe it enacted\b",
        r"\bthis act may be called\b",
        r"\bshort title\b"
    ]

    institutional_patterns = [
        r"lok sabha",
        r"rajya sabha",
        r"government of india",
        r"gazette of india",
        r"ministry of law"
    ]

    structural_hits = sum(1 for p in structural_patterns if re.search(p, text))
    institutional_hits = sum(1 for p in institutional_patterns if re.search(p, text))

    return structural_hits >= 2 and institutional_hits >= 1

# ---------------- PDF GENERATOR ----------------
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

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader(
    "Upload ONLY Government / Parliamentary Bill PDF",
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
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        except:
            pass

    st.session_state.full_text = text

    # -------- STRICT VALIDATION (ONLY FIX HERE) --------
    if not is_government_bill(text):
        st.error(
            "❌ Invalid document.\n\n"
            "Only official Government / Parliamentary Bills are allowed.\n"
            "Circulars, Notifications, Office Orders are rejected."
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
You are a Public Policy Analyst.

Your audience:
• 8th grade school students
• Common citizens with no legal background

Your task:
Analyze ONLY the given bill text.
Do NOT assume anything outside the bill.
Do NOT add external knowledge.

------------------------------------
OUTPUT FORMAT (STRICT)
------------------------------------
Return the response using EXACTLY the following headings.
Do NOT change heading names.
Do NOT add extra headings.
Do NOT add markdown (**, ###, etc).

------------------------------------
SECTOR:
------------------------------------
• Identify the ONE primary sector this bill belongs to
• Use ONLY ONE WORD

------------------------------------
OBJECTIVE:
------------------------------------
• Explain the main objective of the bill
• Use VERY SIMPLE language
• 3 to 5 short lines

------------------------------------
SUMMARY (SIMPLE):
------------------------------------
• 3 to 5 short lines for common citizens

------------------------------------
SUMMARY (DETAILED):
------------------------------------
• 10 to 20 bullet points
• Each bullet = one idea

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
IMPORTANT RULES:
------------------------------------
• Use ONLY the bill text
• No assumptions
• Simple language
• No markdown

------------------------------------
BILL TEXT:
{text[:12000]}
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
    st.write(extract("SUMMARY (SIMPLE):"))

    if st.button("View Detailed Summary"):
        detail = extract("SUMMARY (DETAILED):")
        st.write(detail)
        st.download_button(
            "⬇️ Download PDF",
            create_pdf(detail),
            "Bill_Summary.pdf"
        )

elif st.session_state.view == "impact":
    st.header("📊 Impact")
    st.write(extract("IMPACT ANALYSIS:"))

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

# ---------------- BILL VALIDATOR SETTINGS ----------------
BILL_KEYWORDS = [
    "bill", "act", "speaker", "parliament", "lok sabha", "rajya sabha", 
    "gazette", "legislative", "statement of objects", "enacted", 
    "ministry of law", "commencement", "provisions"
]

def is_likely_bill(text):
    """Initial fast check using keywords."""
    text_lower = text.lower()
    # Check for specific high-confidence phrases
    high_confidence = ["statement of objects and reasons", "be it enacted", "gazette of india"]
    if any(phrase in text_lower for phrase in high_confidence):
        return True
    # Otherwise, check if at least 3 keywords appear
    count = sum(1 for k in BILL_KEYWORDS if k in text_lower)
    return count >= 3

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
        st.error("AI service not configured. Please set GROQ_API_KEY in environment variables.")
        st.stop()

    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

    if st.button("🔍 Generate Analysis"):
        # STEP 1: KEYWORD VALIDATION
        if not is_likely_bill(st.session_state.full_text):
            st.error("❌ Invalid Document: This doesn't look like a Government Bill or Act. Please upload a relevant policy document.")
        else:
            with st.spinner("Analyzing bill..."):
                # STEP 2: LLM VALIDATION + ANALYSIS
                prompt = f"""
You are a Public Policy Analyst. Your users are 8th grade students. 

CRITICAL STEP: 
Check if the following text is a Government Bill, Act, or Policy. 
If it is NOT related to government legislation or policy, return ONLY the phrase: REJECT_DOCUMENT

If it IS a bill, provide the analysis in this EXACT format (no markdown like ** or #):

SECTOR:
(One word: Agri / Finance / Education / Healthcare / Tech / Environment / Defence / Other)

OBJECTIVE:
(3 to 5 short lines)

DETAILED SUMMARY:
(10 to 20 bullet points)

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

TEXT TO ANALYZE:
{st.session_state.full_text[:20000]}
"""
                response = llm.invoke(prompt)
                
                if "REJECT_DOCUMENT" in response.content:
                    st.error("❌ The AI analyzed the content and determined it is not a Government Bill. Analysis cancelled.")
                    st.session_state.analysis = None
                else:
                    st.session_state.analysis = response.content
                    st.session_state.view = "sector" # Set default view

# ---------------- HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content or "REJECT_DOCUMENT" in content:
        return "Not available"
    
    headers = [
        "SECTOR:", "OBJECTIVE:", "DETAILED SUMMARY:",
        "IMPACT ANALYSIS:", "BENEFICIARIES:", "AFFECTED GROUPS:",
        "POSITIVES:", "NEGATIVES / RISKS:"
    ]
    
    try:
        start_idx = content.find(title)
        if start_idx == -1: return "Section not found."
        
        start_pos = start_idx + len(title)
        remaining_content = content[start_pos:]
        
        end_pos = len(remaining_content)
        for h in headers:
            h_idx = remaining_content.find(h)
            if h_idx != -1 and h_idx < end_pos:
                end_pos = h_idx
        
        text = remaining_content[:end_pos].strip()
        for m in ["**", "__", "##", "###"]:
            text = text.replace(m, "")
        return text
    except:
        return "Error extracting section."

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

# ---------------- CONTENT DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.markdown("### 📌 Explore Analysis")
    c1, c2, c3 = st.columns(3)

    if c1.button("🏷️ Sector"): st.session_state.view = "sector"
    if c2.button("📄 Summary"): st.session_state.view = "summary"
    if c3.button("📊 Impact"): st.session_state.view = "impact"

    st.markdown("---")
    if st.session_state.view == "sector":
        st.header("🏷️ Sector")
        st.info(extract("SECTOR:"))

    elif st.session_state.view == "summary":
        st.header("📄 Bill Summary")
        st.subheader("🎯 Objective")
        st.write(extract("OBJECTIVE:"))
        
        with st.expander("📘 View Detailed Summary", expanded=True):
            detail = extract("DETAILED SUMMARY:")
            st.write(detail)
            st.download_button("⬇️ Download PDF", generate_summary_pdf(detail), "Bill_Summary.pdf")

    elif st.session_state.view == "impact":
        st.header("📊 Impact Analysis")
        st.write(extract("IMPACT ANALYSIS:"))
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("✅ Positives")
            st.success(extract("POSITIVES:"))
            st.subheader("💎 Beneficiaries")
            st.write(extract("BENEFICIARIES:"))
        with col_b:
            st.subheader("⚠️ Risks")
            st.error(extract("NEGATIVES / RISKS:"))
            st.subheader("👥 Affected Groups")
            st.write(extract("AFFECTED GROUPS:"))

# ---------------- AI CHAT ----------------
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    user_q = st.text_input("Ask a specific question about a clause or rule:")
    if user_q:
        with st.spinner("Searching bill..."):
            chat_prompt = f"Using this Bill text: {st.session_state.full_text[:15000]}, answer: {user_q}"
            answer = llm.invoke(chat_prompt)
            st.chat_message("assistant").write(answer.content)

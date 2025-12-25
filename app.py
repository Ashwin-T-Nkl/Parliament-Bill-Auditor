import streamlit as st
from pypdf import PdfReader
import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from langchain_groq import ChatGroq

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Parliament Bill Auditor", layout="wide")
st.title("🏛️ Parliament Bill Auditor")

# ---------------- ENHANCED VALIDATION SETTINGS ----------------
BILL_KEYWORDS = [
    "bill", "act", "parliament", "lok sabha", "rajya sabha", "gazette", 
    "legislative", "enacted", "minister", "ministry", "objects and reasons",
    "vidheyak", "adhiniyam", "purasthapit", "introduced", "passed",
    "government", "legislation", "proposed", "sponsored", "amendment"
]

REAL_BILL_PATTERNS = [
    r"a\s+bill\s+to\s+", 
    r"bill\s+no\.?\s*\d+", 
    r"as\s+passed\s+by\s+(lok|rajya)\s+sabha", 
    r"introduced\s+in\s+(lok|rajya)\s+sabha", 
    r"minister\s+of\s+", 
    r"sponsored\s+by", 
    r"statement\s+of\s+objects\s+and\s+reasons", 
    r"financial\s+memorandum", 
]

# ---------------- HELPER FUNCTIONS (DEFINED FIRST) ----------------
def format_as_bullets(text):
    if not text: return ""
    lines = text.strip().split('\n')
    bullet_lines = []
    for line in lines:
        line = line.strip()
        if line:
            if not line.startswith('-'):
                bullet_lines.append(f"- {line}")
            else:
                bullet_lines.append(line)
    return '\n'.join(bullet_lines)

def parse_analysis_data(analysis_text):
    if not analysis_text: return {}
    sections = {}
    headers = [
        "SECTOR:", "OBJECTIVE:", "DETAILED SUMMARY:", "IMPACT ANALYSIS:",
        "BENEFICIARIES:", "AFFECTED GROUPS:", "POSITIVES:", "NEGATIVES / RISKS:"
    ]
    for i in range(len(headers)):
        header = headers[i]
        start_idx = analysis_text.find(header)
        if start_idx != -1:
            start_idx += len(header)
            end_idx = len(analysis_text)
            for j in range(i + 1, len(headers)):
                next_header_pos = analysis_text.find(headers[j], start_idx)
                if next_header_pos != -1 and next_header_pos < end_idx:
                    end_idx = next_header_pos
                    break
            section_text = analysis_text[start_idx:end_idx].strip()
            section_key = header.replace(":", "").lower().replace(" ", "_")
            sections[section_key] = format_as_bullets(section_text)
    return sections

def is_valid_government_doc(text):
    text_lower = text.lower()
    if len(text.strip()) < 500:
        return False, "Document too short (less than 500 characters)"
    strong_indicators = 0
    for pattern in REAL_BILL_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            strong_indicators += 1
    keyword_count = sum(1 for k in BILL_KEYWORDS if k in text_lower)
    if strong_indicators >= 2 and keyword_count >= 5:
        return True, "✅ Valid parliamentary bill detected"
    elif strong_indicators >= 1 and keyword_count >= 3:
        return True, "⚠️ Possible bill detected - proceeding with analysis"
    else:
        return False, "❌ Document doesn't appear to be a parliamentary bill"

def extract_section(section_name):
    if not st.session_state.get('analysis_data'):
        return "Analysis not yet generated."
    section_key = section_name.lower().replace(" ", "_")
    return st.session_state.analysis_data.get(section_key, "Section not found in analysis.")

def generate_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica", 10)
    lines = text.split("\n")
    for line in lines:
        if y < 50: 
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica", 10)
        if line.startswith('-'):
            pdf.drawString(60, y, "• " + line[1:].strip())
        else:
            pdf.drawString(50, y, line)
        y -= 15
    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- SESSION STATE ----------------
if "analysis" not in st.session_state: st.session_state.analysis = None
if "full_text" not in st.session_state: st.session_state.full_text = ""
if "last_file" not in st.session_state: st.session_state.last_file = None
if "validation_status" not in st.session_state: st.session_state.validation_status = None
if "analysis_data" not in st.session_state: st.session_state.analysis_data = {}

# ---------------- FILE UPLOAD & LOGIC ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.validation_status = None
        st.session_state.analysis_data = {}
        
        reader = PdfReader(uploaded_file)
        raw_text = ""
        for page in reader.pages:
            try:
                t = page.extract_text()
                if t: raw_text += t + "\n"
            except: pass
        st.session_state.full_text = raw_text
        st.session_state.validation_status = is_valid_government_doc(raw_text)

    if st.session_state.validation_status:
        is_valid, message = st.session_state.validation_status
        if not is_valid:
            st.error(message)
            st.stop()
        else:
            st.success(message)

    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY.")
        st.stop()

    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.1, max_tokens=3500)

    # Injecting CSS for Green Button
    st.markdown("""<style>div.stButton > button:first-child { background-color: #28a745; color: white; }</style>""", unsafe_allow_html=True)

    if st.button("🔍 Generate Analysis", type="primary"):
        with st.spinner("Analyzing document..."):
            prompt = f"SYSTEM: Policy Analyst for 8th graders. Analyze based ONLY on text: {st.session_state.full_text[:15000]}"
            # (Note: Using your preferred detailed prompt here in actual deployment)
            try:
                response = llm.invoke(prompt)
                st.session_state.analysis = response.content
                st.session_state.analysis_data = parse_analysis_data(response.content)
            except Exception as e:
                st.error(f"Error during analysis: {e}")

# ---------------- UI DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    tabs = st.tabs(["Sector", "Summary", "Impact", "Details"])
    # (Rest of your UI tab logic remains same as provided in your version)

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

# ---------------- ROBUST VALIDATION ----------------
# Keywords to catch documents like Immigration, Sea Carriage, and Chit Fund bills
BILL_KEYWORDS = [
    "bill", "act", "parliament", "lok sabha", "rajya sabha", "gazette", 
    "legislative", "enacted", "item no", "clause", "minister", "ministry",
    "objects and reasons", "vidheyak", "adhiniyam", "prastav", "purasthapit"
]

def clean_parliamentary_text(text):
    """
    Fixed the SyntaxError here by using proper regex strings.
    This removes tags to help the AI focus on the actual law.
    """
    # Using a raw string r'' and escaping the brackets correctly
    text = re.sub(r'\', '', text)
    return ' '.join(text.split())

def is_valid_government_doc(text):
    """Returns True if the document contains core legislative keywords."""
    if len(text.strip()) < 100: return False
    text_lower = text.lower()
    return any(k in text_lower for k in BILL_KEYWORDS)

# ---------------- SESSION STATE ----------------
if "analysis" not in st.session_state: st.session_state.analysis = None
if "full_text" not in st.session_state: st.session_state.full_text = ""
if "last_file" not in st.session_state: st.session_state.last_file = None

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        
        reader = PdfReader(uploaded_file)
        raw_text = ""
        for page in reader.pages:
            try:
                t = page.extract_text()
                if t: raw_text += t + "\n"
            except: pass
        
        # Clean the text using the fixed function
        st.session_state.full_text = clean_parliamentary_text(raw_text)

    if "GROQ_API_KEY" not in os.environ:
        st.error("AI service not configured. Please set GROQ_API_KEY in environment variables.")
        st.stop()

    llm = ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

    if st.button("🔍 Generate Analysis"):
        if not is_valid_government_doc(st.session_state.full_text):
            st.warning("⚠️ This document might not be a standard Bill, but I will try to analyze it anyway.")
        
        with st.spinner("Analyzing document..."):
            prompt = f"""
            You are a Public Policy Analyst for 8th grade students.
            Analyze the provided Bill/Policy text. Use ONLY the provided text.
            Do NOT use markdown symbols like ** or #. Follow the headings exactly.

            SECTOR:
            (Agri / Finance / Education / Healthcare / Tech / Environment / Defence / Other)

            OBJECTIVE:
            (3 to 5 short lines explaining why this bill exists)

            DETAILED SUMMARY:
            (10 to 20 simple bullet points)

            IMPACT ANALYSIS:
            Citizens:
            - Bullet points
            Businesses:
            - Bullet points
            Government:
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
            {st.session_state.full_text[:18000]}
            """
            try:
                response = llm.invoke(prompt)
                st.session_state.analysis = response.content
            except Exception as e:
                st.error(f"AI Error: {e}")

# ---------------- EXTRACTION HELPER ----------------
def extract(title):
    content = st.session_state.analysis
    if not content: return "No analysis available."
    
    markers = ["SECTOR:", "OBJECTIVE:", "DETAILED SUMMARY:", "IMPACT ANALYSIS:", 
               "BENEFICIARIES:", "AFFECTED GROUPS:", "POSITIVES:", "NEGATIVES / RISKS:"]
    
    try:
        start = content.find(title)
        if start == -1: return "Section not found."
        start += len(title)
        
        end = len(content)
        for m in markers:
            pos = content.find(m, start)
            if pos != -1 and pos < end:
                end = pos
        
        return content[start:end].strip()
    except:
        return "Error parsing section."

def generate_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica", 10)
    for line in text.split("\n"):
        if y < 50: pdf.showPage(); y = 800
        pdf.drawString(50, y, line[:95])
        y -= 15
    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- CONTENT DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["🏷️ Sector", "📄 Summary", "📊 Impact Analysis"])

    with tab1:
        st.header("🏷️ Identified Sector")
        st.info(extract("SECTOR:"))

    with tab2:
        st.header("📄 Bill Summary")
        st.subheader("🎯 Main Objective")
        st.write(extract("OBJECTIVE:"))
        
        st.subheader("💡 Key Provisions")
        detail = extract("DETAILED SUMMARY:")
        st.write(detail)
        st.download_button("⬇️ Download Summary PDF", generate_pdf(detail), "Detailed_Summary.pdf")

    with tab3:
        st.header("📊 Impact & Risks")
        st.write(extract("IMPACT ANALYSIS:"))
        
        col1, col2 = st.columns(2)
        with col1:
            st.success("✅ Positives\n\n" + extract("POSITIVES:"))
            st.write("**💎 Who gains?**\n", extract("BENEFICIARIES:"))
        with col2:
            st.error("⚠️ Risks\n\n" + extract("NEGATIVES / RISKS:"))
            st.write("**👥 Who is affected?**\n", extract("AFFECTED GROUPS:"))

# ---------------- AI CHAT ----------------
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask a Specific Question")
    user_q = st.text_input("Ask a question about a clause or rule:")
    if user_q:
        with st.spinner("Checking bill text..."):
            ans = llm.invoke(f"Using this bill text: {st.session_state.full_text[:12000]}, answer: {user_q}")
            st.chat_message("assistant").write(ans.content)

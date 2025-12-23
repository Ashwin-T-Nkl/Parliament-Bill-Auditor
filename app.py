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

# ---------------- SESSION STATE ----------------
if "view" not in st.session_state:
    st.session_state.view = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "last_file" not in st.session_state:
    st.session_state.last_file = None
if "full_text" not in st.session_state:
    st.session_state.full_text = ""

# ---------------- TEXT CLEANING HELPER ----------------
def clean_for_ai(text):
    """
    Removes the '' tags and backslashes. 
    These patterns are the reason the AI glitches into numerical answers.
    """
    # 1. Removes any text inside square brackets like 
    cleaned = re.sub(r'\', '', text)
    # 2. Removes standard bracketed numbers like [110]
    cleaned = re.sub(r'\[\d+\]', '', cleaned)
    # 3. Removes literal backslashes to prevent SyntaxErrors
    cleaned = cleaned.replace('\\', '')
    return cleaned.strip()

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.view = None
        st.session_state.full_text = ""

        # Extracting text using pypdf
        reader = PdfReader(uploaded_file)
        raw_text = ""
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text:
                    raw_text += text + "\n"
            except:
                pass
        
        # Clean text immediately after extraction
        st.session_state.full_text = clean_for_ai(raw_text)

    # API Configuration
    if "GROQ_API_KEY" not in os.environ:
        st.error("GROQ_API_KEY not found in environment variables.")
        st.stop()

    llm = ChatGroq(
        model_name="llama-3.1-8b-instant",
        temperature=0.1  # Set to 0.1 to help avoid repeating loops
    )

    if st.button("🔍 Generate Analysis"):
        with st.spinner("Analyzing bill..."):
            prompt = f"""
You are a Public Policy Analyst.
Audience: 8th grade students and common citizens.
Use very simple language.

Return EXACTLY the following headings and follow the rules strictly.

SECTOR:
- ONE word only

OBJECTIVE:
- 3 to 5 short lines

SIMPLE SUMMARY:
- 3 to 5 short lines

DETAILED SUMMARY:
- 10 to 20 bullet points

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

Rules:
- Use ONLY the bill text
- No assumptions
- No markdown symbols (** ### etc)
- Follow bullet rules strictly

BILL TEXT:
{st.session_state.full_text[:20000]}
"""
            response = llm.invoke(prompt)
            st.session_state.analysis = response.content
            st.session_state.view = None

# ---------------- NAVIGATION ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.markdown("### 📌 Explore Analysis")
    c1, c2, c3 = st.columns(3)

    if c1.button("🏷️ Sector"):
        st.session_state.view = "sector"
    if c2.button("📄 Summary"):
        st.session_state.view = "summary"
    if c3.button("📊 Impact"):
        st.session_state.view = "impact"

# ---------------- DATA EXTRACTION HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content:
        return "Not available"
    
    headers = [
        "SECTOR:", "OBJECTIVE:", "SIMPLE SUMMARY:", "DETAILED SUMMARY:",
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
        # Remove any stray markdown
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
st.markdown("---")

if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.info(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Bill Summary")
    st.subheader("🎯 Objective")
    st.write(extract("OBJECTIVE:"))
    st.subheader("💡 Simple Overview")
    st.write(extract("SIMPLE SUMMARY:"))

    with st.expander("📘 View Detailed Summary"):
        detail = extract("DETAILED SUMMARY:")
        st.write(detail)
        st.download_button(
            "⬇️ Download Detailed Summary (PDF)",
            generate_summary_pdf(detail),
            "Bill_Detailed_Summary.pdf",
            "application/pdf"
        )

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")
    st.write(extract("IMPACT ANALYSIS:"))
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("✅ Positives")
        st.success(extract("POSITIVES:"))
    with col_b:
        st.subheader("⚠️ Risks")
        st.error(extract("NEGATIVES / RISKS:"))

# ---------------- AI CHAT ----------------
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    user_q = st.text_input("Ask a specific question about a clause or rule:")

    if user_q:
        with st.spinner("Thinking..."):
            chat_prompt = f"""
            Answer the question using ONLY the provided Bill text.
            If the answer is not mentioned, say 'Not mentioned in the document'.
            
            RULES:
            - Answer in full sentences.
            - DO NOT output long lists of numbers or source tags.

            BILL TEXT:
            {st.session_state.full_text[:20000]}

            QUESTION:
            {user_q}
            """
            answer = llm.invoke(chat_prompt)
            st.chat_message("assistant").write(answer.content)

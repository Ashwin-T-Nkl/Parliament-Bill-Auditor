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

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

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
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            except:
                pass
        st.session_state.full_text = full_text

    if "GROQ_API_KEY" not in os.environ:
        st.error("AI service not configured. Please set GROQ_API_KEY in environment variables.")
        st.stop()

    llm = ChatGroq(
        model_name="llama-3.1-8b-instant",
        temperature=0
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

# ---------------- HELPERS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content:
        return "Not available"
    
    # List of all possible headers to find the boundaries
    headers = [
        "SECTOR:", "OBJECTIVE:", "SIMPLE SUMMARY:", "DETAILED SUMMARY:",
        "IMPACT ANALYSIS:", "BENEFICIARIES:", "AFFECTED GROUPS:",
        "POSITIVES:", "NEGATIVES / RISKS:"
    ]
    
    try:
        # Find the start of the requested section
        start_idx = content.find(title)
        if start_idx == -1: return "Section not found."
        
        start_pos = start_idx + len(title)
        
        # Find the start of the NEXT section to crop the text
        remaining_content = content[start_pos:]
        end_pos = len(remaining_content)
        
        for h in headers:
            h_idx = remaining_content.find(h)
            if h_idx != -1 and h_idx < end_pos:
                end_pos = h_idx
        
        text = remaining_content[:end_pos].strip()
        
        # CLEAN MARKDOWN JUNK
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
        # Basic line wrapping logic
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
        with st.spinner("Searching bill text..."):
            chat_prompt = f"""
            Answer the question based on the Parliamentary Bill text below.
            If the answer isn't in the text, say you don't know.

            BILL TEXT:
            {st.session_state.full_text[:20000]}

            QUESTION:
            {user_q}
            """
            answer = llm.invoke(chat_prompt)
            st.chat_message("assistant").write(answer.content)

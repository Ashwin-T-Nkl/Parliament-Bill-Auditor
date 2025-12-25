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
        st.session_state.full_text = raw_text

    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY in secrets.")
        st.stop()

    # SWITCHED TO 70B MODEL: Much more stable and powerful for complex bills
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile", 
        temperature=0.1,
        max_tokens=3000
    )

    if st.button("🔍 Generate Analysis"):
        with st.spinner("Analyzing document with high-power AI..."):
            # SYSTEM PROMPT: Forces the model to stick to the format and avoid loops
            prompt = f"""
            You are an expert Public Policy Analyst. 
            Explain this Bill to an 8th-grade student. Use simple language.
            
            STRICT RULES:
            1. Use ONLY the provided text.
            2. Do NOT use markdown symbols like **, ##, or #.
            3. Do NOT count or generate random number sequences.
            4. Start each section EXACTLY with the header name.

            SECTOR:
            (Agri / Finance / Education / Healthcare / Tech / Environment / Defence / Other)

            OBJECTIVE:
            (Explain why this bill exists in 3 lines)

            DETAILED SUMMARY:
            (Provide 10 to 15 simple bullet points)

            CITIZENS IMPACT:
            (Bullet points)

            BUSINESS IMPACT:
            (Bullet points)

            POSITIVES:
            (Bullet points)

            RISKS:
            (Bullet points)

            TEXT:
            {st.session_state.full_text[:15000]}
            """
            try:
                response = llm.invoke(prompt)
                st.session_state.analysis = response.content
            except Exception as e:
                st.error(f"Model Error: {e}")

# ---------------- EXTRACTION HELPER ----------------
def extract(title):
    content = st.session_state.analysis
    if not content: return "Processing..."
    
    # List of keys to look for in the AI response
    keys = ["SECTOR:", "OBJECTIVE:", "DETAILED SUMMARY:", "CITIZENS IMPACT:", 
            "BUSINESS IMPACT:", "POSITIVES:", "RISKS:"]
    
    try:
        if title not in content: return f"{title} not found."
        start = content.find(title) + len(title)
        
        # Find the next key to end the slice
        end = len(content)
        for k in keys:
            k_pos = content.find(k, start)
            if k_pos != -1 and k_pos < end:
                end = k_pos
        
        return content[start:end].strip()
    except:
        return "Extraction failed."

# ---------------- UI DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    # Using Tabs for a clean, non-crashing interface
    t1, t2, t3 = st.tabs(["🏷️ Sector", "📄 Summary", "📊 Impact"])

    with t1:
        st.info(f"**Primary Sector:** {extract('SECTOR:')}")

    with t2:
        st.subheader("🎯 Objective")
        st.write(extract("OBJECTIVE:"))
        st.subheader("💡 Key Points")
        st.write(extract("DETAILED SUMMARY:"))

    with t3:
        col1, col2 = st.columns(2)
        with col1:
            st.success("✅ **Positives**\n\n" + extract("POSITIVES:"))
            st.write("**Impact on Citizens:**\n", extract("CITIZENS IMPACT:"))
        with col2:
            st.error("⚠️ **Risks**\n\n" + extract("RISKS:"))
            st.write("**Impact on Businesses:**\n", extract("BUSINESS IMPACT:"))

# ---------------- CHAT ----------------
if st.session_state.analysis:
    st.markdown("---")
    st.header("💬 Ask a Question")
    q = st.text_input("Ask about a specific rule or person mentioned:")
    if q:
        with st.spinner("Searching..."):
            ans = llm.invoke(f"Context: {st.session_state.full_text[:10000]}\nQuestion: {q}")
            st.chat_message("assistant").write(ans.content)

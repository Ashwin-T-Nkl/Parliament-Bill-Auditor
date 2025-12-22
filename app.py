import streamlit as st
from pypdf import PdfReader
import os

st.set_page_config(page_title="Parliament Bill Auditor")

st.title("🏛️ Parliament Bill Auditor")


# Check if Groq key exists (Cloud only)
GROQ_AVAILABLE = "GROQ_API_KEY" in os.environ

uploaded_file = st.file_uploader(
    "Upload Bill PDF",
    type=["pdf"]
)

if uploaded_file is not None:
    reader = PdfReader(uploaded_file)

    full_text = ""

    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text:
                full_text += text
        except Exception:
            # Skip pages with extraction issues
            continue


    st.success("PDF uploaded and read successfully!")

    # --- Bill validation ---
    preview_text = full_text[:4000].lower()

    keywords = [
        "bill", "act", "parliament", "parliament of india",
        "lok sabha", "rajya sabha", "government of india",
        "gazette", "legislative", "statement of objects",
        "statement of objects and reasons", "extent", "commencement"
    ]

    is_bill = any(k in preview_text for k in keywords)

    if is_bill:
        st.success("✅ This document appears to be a Parliamentary Bill.")

        if not GROQ_AVAILABLE:
            st.info(
                "ℹ️ AI analysis is disabled locally.\n\n"
                "It will automatically activate after deployment "
                "when GROQ_API_KEY is added in Streamlit Cloud."
            )
        else:
            from langchain_groq import ChatGroq

            llm = ChatGroq(
                model_name="llama-3.3-70b-versatile",
                temperature=0
            )

            if st.button("🔍 Generate AI Summary"):
                with st.spinner("Analyzing bill using Groq..."):
                    prompt = f"""
                    You are a Public Policy Analyst.

                    Analyze the following Parliamentary Bill and return the output in
                    CLEARLY SEPARATED SECTIONS using simple language (8th-grade level).

                    Provide:

                    1. SECTOR:
                    (Choose one or more: Agriculture, Finance, Education, Healthcare,
                    Technology, Environment, Defence, Governance, Social Welfare)

                    2. OBJECTIVE OF THE BILL:
                    (Why was this bill introduced?)

                    3. SIMPLIFIED SUMMARY:
                    (10–12 easy-to-understand lines for a common citizen)

                    4. SHORT-TERM IMPACT (0–1 year):
                    (Bullet points)

                    5. MEDIUM-TERM IMPACT (1–5 years):
                    (Bullet points)

                    6. LONG-TERM IMPACT (5+ years):
                    (Bullet points)

                    7. POSITIVES:
                    (Bullet points)

                    8. NEGATIVES / RISKS:
                    (Bullet points)

                    Only use the information from the bill text.
                    Do not add assumptions.




BILL TEXT:
{full_text[:12000]}
"""
                    response = llm.invoke(prompt)

                st.subheader("📄 AI Summary")
                st.write(response.content)

    else:
        st.warning("⚠️ This document may NOT be a Parliamentary Bill.")

    st.subheader("Preview (first 500 characters)")
    st.text(full_text[:500])


# streamlit run c:/Users/Ashwin/Documents/Tech/Bill/app.py 

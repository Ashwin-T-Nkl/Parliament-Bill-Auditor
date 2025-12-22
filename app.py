import streamlit as st
from pypdf import PdfReader
import os

st.set_page_config(page_title="Parliament Bill Auditor")

st.title("🏛️ Parliament Bill Auditor")
st.write("Upload a Parliamentary Bill PDF to begin analysis.")

# Check if Groq key exists (Cloud only)
GROQ_AVAILABLE = "GROQ_API_KEY" in os.environ

uploaded_file = st.file_uploader(
    "Step 1: Upload Bill PDF",
    type=["pdf"]
)

if uploaded_file is not None:
    reader = PdfReader(uploaded_file)

    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""

    st.success("PDF uploaded and read successfully!")

    # --- Bill validation ---
    preview_text = full_text[:4000].lower()

    keywords = [
        "bill", "act", "parliament", "parliament of india",
        "lok sabha", "rajya sabha", "government of india",
        "gazette", "legislative", "statement of objects",
        "statement of objects and reasons",
        "short title", "extent", "commencement"
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
Summarize the following Parliamentary Bill in simple English.
Keep it under 10 lines.

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

import streamlit as st
from pypdf import PdfReader
import os

st.set_page_config(page_title="Parliament Bill Auditor", layout="wide")

st.title("🏛️ Parliament Bill Auditor")

# ---------- File Upload ----------
uploaded_file = st.file_uploader(
    "Upload Bill PDF",
    type=["pdf"]
)

if uploaded_file:
    reader = PdfReader(uploaded_file)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() or ""

    # ---------- Groq Availability ----------
    GROQ_AVAILABLE = "GROQ_API_KEY" in os.environ

    if GROQ_AVAILABLE:
        from langchain_groq import ChatGroq

        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )

        if st.button("🔍 Generate Analysis"):
            with st.spinner("Analyzing bill…"):
                prompt = f"""
You are a Public Policy Analyst.

Analyze the following Parliamentary Bill and respond in clearly
labeled sections using simple, citizen-friendly language.

Provide:

SECTOR:
(Choose ONE most relevant sector)

SUMMARY:
(Simple explanation for common citizens)

IMPACT:
Short-term (0–1 year)
Medium-term (1–5 years)
Long-term (5+ years)

BENEFICIARIES:
(Who benefits?)

AFFECTED GROUPS:
(Who may be negatively affected?)

POSITIVES:
(Bullet points)

NEGATIVES / RISKS:
(Bullet points)

Only use the bill text.
Do not assume information.

BILL TEXT:
{full_text[:12000]}
"""
                response = llm.invoke(prompt)
                content = response.content

            # ---------- Basic Section Extraction ----------
            def get_section(title):
                if title not in content:
                    return "Not specified"
                part = content.split(title)[1]
                return part.split("\n\n")[0].strip()

            sector = get_section("SECTOR")
            summary = get_section("SUMMARY")
            impact = get_section("IMPACT")
            beneficiaries = get_section("BENEFICIARIES")
            affected = get_section("AFFECTED GROUPS")
            positives = get_section("POSITIVES")
            negatives = get_section("NEGATIVES")

            # ---------- Tiles Layout ----------
            st.markdown("### 📌 Bill Overview")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Sector", sector)

            with col2:
                with st.expander("📄 Summary"):
                    st.write(summary)

            with col3:
                with st.expander("📊 Impact Analysis"):
                    st.markdown("**Impact (Short / Medium / Long Term)**")
                    st.write(impact)

                    st.markdown("**Who Benefits**")
                    st.write(beneficiaries)

                    st.markdown("**Who Is Affected**")
                    st.write(affected)

                    st.markdown("**Positives**")
                    st.write(positives)

                    st.markdown("**Negatives / Risks**")
                    st.write(negatives)

            # ---------- AI Chat Placeholder ----------
            st.markdown("---")
            st.markdown("### 💬 Ask AI about this Bill")
            st.info("Chat feature can be enabled next (optional as per project doc).")

    else:
        st.warning("AI analysis is currently unavailable.")

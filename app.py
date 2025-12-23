import streamlit as st
from pypdf import PdfReader
import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Parliament Bill Auditor",
    layout="wide"
)

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

is_bill = False  # default

if uploaded_file:
    # Reset state on new file
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
                full_text += text
        except:
            continue

    st.session_state.full_text = full_text

    # ---------------- BILL VALIDATION ----------------
    preview_text = full_text[:4000].lower()

    bill_keywords = [
        "bill",
        "act",
        "parliament",
        "parliament of india",
        "lok sabha",
        "rajya sabha",
        "government of india",
        "gazette",
        "legislative",
        "statement of objects",
        "statement of objects and reasons",
        "extent",
        "commencement",
        "enacted",
        "ministry of law"
    ]

    is_bill = any(keyword in preview_text for keyword in bill_keywords)

    if not is_bill:
        st.warning("📄 Kindly upload a Parliamentary Bill–related PDF to continue.")

    # ---------------- GROQ ----------------
    if is_bill and "GROQ_API_KEY" in os.environ:
        from langchain_groq import ChatGroq

        llm = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )

        if st.button("🔍 Generate Analysis"):
            with st.spinner("Analyzing bill..."):
                prompt = f"""
You are a Public Policy Analyst.

Your readers are 8th Grade School students and common citizens.

Return clearly labeled sections using simple language.

SECTOR:
One word primary sector (e.g., Finance, Agriculture, Transport, Energy, Shipping).

OBJECTIVE:
Explain the main objective of this bill in 3–4 simple lines.

SUMMARY (DETAILED):
Provide a 10–20 bullet point explanation:
- What the bill does
- Why it matters
- What changes for a normal person

IMPACT ANALYSIS:
Explain the impact separately for each group:

Citizens:
(Bullet points)

Businesses:
(Bullet points)

Government:
(Bullet points)

Industries / Markets:
(Bullet points)

NGOs / Civil Society:
(Bullet points)

BENEFICIARIES:
Clearly mention:
- Which sectors benefit
- Which sectors get new business or growth opportunities

AFFECTED GROUPS:
Clearly mention:
- Which sectors face restrictions
- Which sectors face higher costs, compliance, or limitations

POSITIVES:
(Bullet points focusing on advantages and opportunities)

NEGATIVES / RISKS:
(Bullet points focusing on risks, costs, resistance, or implementation challenges)

Rules:
- Use only the bill text
- Do not assume facts
- Keep language simple

BILL TEXT:
{st.session_state.full_text[:12000]}
"""
                response = llm.invoke(prompt)
                st.session_state.analysis = response.content
                st.session_state.view = None

# ---------------- TILE NAVIGATION ----------------
if st.session_state.analysis:
    st.markdown("### 📌 Explore Analysis")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("🏷️ Sector"):
            st.session_state.view = "sector"

    with c2:
        if st.button("📄 Summary"):
            st.session_state.view = "summary"

    with c3:
        if st.button("📊 Impact"):
            st.session_state.view = "impact"

# ---------------- HELPER FUNCTIONS ----------------
def extract(title):
    content = st.session_state.analysis
    if not content or title not in content:
        return "Not available"

    text = content.split(title)[1].split("\n\n")[0]
    text = text.replace("**", "").strip()
    return text

def generate_summary_pdf(text):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    pdf.setFont("Helvetica", 10)

    for line in text.split("\n"):
        if y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = height - 50
        pdf.drawString(40, y, line[:100])
        y -= 14

    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- CONTENT VIEW ----------------
st.markdown("---")

if st.session_state.view == "sector":
    st.header("🏷️ Sector")
    st.markdown(extract("SECTOR:"))

elif st.session_state.view == "summary":
    st.header("📄 Bill Summary")

    st.subheader("🎯 Objective")
    st.markdown(extract("OBJECTIVE:"))

    if st.button("📘 View Detailed Summary"):
        st.subheader("🧾 Detailed Summary")
        detailed_summary = extract("SUMMARY (DETAILED):")
        st.markdown(detailed_summary)

        pdf_file = generate_summary_pdf(detailed_summary)

        st.download_button(
            "⬇️ Download Detailed Summary (PDF)",
            data=pdf_file,
            file_name="Bill_Detailed_Summary.pdf",
            mime="application/pdf"
        )

elif st.session_state.view == "impact":
    st.header("📊 Impact Analysis")

    st.subheader("Impact by Stakeholder")
    st.markdown(extract("IMPACT ANALYSIS:"))

    st.subheader("Beneficiaries (Industries & Sectors)")
    st.markdown(extract("BENEFICIARIES:"))

    st.subheader("Affected Groups (Restrictions & Costs)")
    st.markdown(extract("AFFECTED GROUPS:"))

    st.subheader("Positives")
    st.markdown(extract("POSITIVES:"))

    st.subheader("Risks / Negatives")
    st.markdown(extract("NEGATIVES / RISKS:"))

# ---------------- AI CHAT ----------------
if is_bill and st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")

    user_q = st.text_input("Ask a question")

    if user_q:
        with st.spinner("Thinking..."):
            chat_prompt = f"""
You are answering questions based ONLY on the original Parliamentary Bill text below.

Rules:
- Use only the bill text
- Do NOT use prior summaries or analysis
- Explain answers in simple, citizen-friendly English
- If the bill does not mention the answer, clearly say so

BILL TEXT:
{st.session_state.full_text[:12000]}

QUESTION:
{user_q}
"""
            answer = llm.invoke(chat_prompt)
            st.write(answer.content)

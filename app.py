import streamlit as st
from pypdf import PdfReader
import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from langchain_groq import ChatGroq

# ==================== FUNCTION DEFINITIONS (FIRST!) ====================

def is_valid_government_doc(text):
    """Enhanced validation to distinguish real parliamentary bills from examples"""
    text_lower = text.lower()
    
    if len(text.strip()) < 500:
        return False, "Document too short (less than 500 characters)"
    
    REAL_BILL_PATTERNS = [
        r"a\s+bill\s+to\s+",
        r"bill\s+no\.?\s*\d+",
        r"as\s+passed\s+by\s+(lok|rajya)\s+sabha",
        r"introduced\s+in\s+(lok|rajya)\s+sabha",
        r"statement\s+of\s+objects\s+and\s+reasons",
    ]
    
    BILL_KEYWORDS = [
        "bill", "act", "parliament", "lok sabha", "rajya sabha", 
        "minister", "ministry", "government", "legislation"
    ]
    
    strong_indicators = sum(1 for pattern in REAL_BILL_PATTERNS if re.search(pattern, text_lower, re.IGNORECASE))
    keyword_count = sum(1 for k in BILL_KEYWORDS if k in text_lower)
    
    if strong_indicators >= 2 and keyword_count >= 5:
        return True, "✅ Valid parliamentary bill detected"
    elif strong_indicators >= 1 and keyword_count >= 3:
        return True, "⚠️ Possible bill detected"
    else:
        return False, "❌ Not a valid parliamentary bill"

def extract_section_from_analysis(section_name, analysis_text):
    """Extract a specific section from the analysis text"""
    if not analysis_text:
        return "No analysis available."
    
    # Look for section header
    headers = ["SECTOR:", "OBJECTIVE:", "DETAILED SUMMARY:", "IMPACT ANALYSIS:", 
               "BENEFICIARIES:", "AFFECTED GROUPS:", "POSITIVES:", "NEGATIVES / RISKS:"]
    
    target_header = None
    for header in headers:
        if section_name.upper() in header:
            target_header = header
            break
    
    if not target_header:
        return f"Section '{section_name}' not found."
    
    start_idx = analysis_text.find(target_header)
    if start_idx == -1:
        return f"Section '{section_name}' not found in analysis."
    
    start_idx += len(target_header)
    end_idx = len(analysis_text)
    
    # Find next section
    for header in headers:
        if header == target_header:
            continue
        next_pos = analysis_text.find(header, start_idx)
        if next_pos != -1 and next_pos < end_idx:
            end_idx = next_pos
    
    return analysis_text[start_idx:end_idx].strip()

def generate_pdf(text):
    """Generate PDF from text"""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica", 10)
    
    for line in text.split("\n"):
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

# ==================== STREAMLIT APP ====================

# Page config
st.set_page_config(page_title="Parliament Bill Auditor", layout="wide")
st.title("🏛️ Parliament Bill Auditor")

# Initialize session state
if "analysis" not in st.session_state: 
    st.session_state.analysis = None
if "full_text" not in st.session_state: 
    st.session_state.full_text = ""
if "last_file" not in st.session_state: 
    st.session_state.last_file = None
if "validation_status" not in st.session_state: 
    st.session_state.validation_status = None

# File upload
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.validation_status = None
        
        # Extract text
        reader = PdfReader(uploaded_file)
        raw_text = ""
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text: 
                    raw_text += text + "\n"
            except: 
                pass
        
        st.session_state.full_text = raw_text
        
        # Validate document
        is_valid, message = is_valid_government_doc(raw_text)
        st.session_state.validation_status = (is_valid, message)
    
    # Show validation status
    if st.session_state.validation_status:
        is_valid, message = st.session_state.validation_status
        
        if not is_valid:
            st.error(message)
            st.warning("Upload a real parliamentary bill with 'A BILL TO...', bill number, or mentions of Parliament/Lok Sabha/Rajya Sabha.")
            st.stop()
        else:
            st.success(message)

    # Check API key
    if "GROQ_API_KEY" not in os.environ:
        st.error("Set GROQ_API_KEY environment variable.")
        st.stop()

    # Initialize LLM
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile", 
        temperature=0.1, 
        max_tokens=3500
    )

    # Generate Analysis Button
    if st.button("🔍 Generate Analysis", type="primary"):
        with st.spinner("Analyzing document..."):
            prompt = f"""
You are a Policy Analyst. Analyze this parliamentary bill for students.

CRITICAL FORMAT:
- Use EXACT headings below
- Each section: bullet points starting with -
- No markdown (** or #)
- Simple language

SECTIONS (use these exact headings):

SECTOR:
- [One sector: Agriculture, Finance, Education, Healthcare, Technology, Environment, Defence, Transport, etc.]

OBJECTIVE:
- [Bullet 1]
- [Bullet 2]
- [Bullet 3]
- [Bullet 4]

DETAILED SUMMARY:
- [Key provision 1]
- [Key provision 2]
- [Key provision 3]
- [10-15 total provisions]

IMPACT ANALYSIS:
Citizens:
- [Impact 1]
- [Impact 2]
- [Impact 3]

Businesses:
- [Impact 1]
- [Impact 2]
- [Impact 3]

Government:
- [Impact 1]
- [Impact 2]
- [Impact 3]

BENEFICIARIES:
- [Group 1]
- [Group 2]
- [Group 3]
- [Group 4]

AFFECTED GROUPS:
- [Group 1]
- [Group 2]
- [Group 3]
- [Group 4]

POSITIVES:
- [Positive 1]
- [Positive 2]
- [Positive 3]
- [Positive 4]

NEGATIVES / RISKS:
- [Risk 1]
- [Risk 2]
- [Risk 3]
- [Risk 4]

BILL TEXT:
{st.session_state.full_text[:15000]}
"""
            try:
                response = llm.invoke(prompt)
                st.session_state.analysis = response.content
            except Exception as e:
                st.error(f"Analysis error: {e}")

# Display Analysis
if st.session_state.analysis:
    st.markdown("---")
    
    # Create tabs
    sector_tab, summary_tab, impact_tab, details_tab = st.tabs(["Sector", "Summary", "Impact", "Details"])

    with sector_tab:
        st.header("Sector")
        sector_content = extract_section_from_analysis("SECTOR", st.session_state.analysis)
        st.write(sector_content)

    with summary_tab:
        st.header("Summary")
        
        st.subheader("Objective")
        objective = extract_section_from_analysis("OBJECTIVE", st.session_state.analysis)
        st.write(objective)
        
        st.subheader("Detailed Summary")
        summary = extract_section_from_analysis("DETAILED SUMMARY", st.session_state.analysis)
        st.write(summary)
        
        if summary and "not found" not in summary.lower():
            pdf_text = f"Objective:\n{objective}\n\nDetailed Summary:\n{summary}"
            st.download_button(
                "⬇️ Download PDF Summary",
                generate_pdf(pdf_text),
                "Bill_Summary.pdf",
                "application/pdf"
            )

    with impact_tab:
        st.header("Impact Analysis")
        
        impact = extract_section_from_analysis("IMPACT ANALYSIS", st.session_state.analysis)
        st.write(impact)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("✅ Positives")
            positives = extract_section_from_analysis("POSITIVES", st.session_state.analysis)
            st.write(positives)
            
            st.subheader("Beneficiaries")
            beneficiaries = extract_section_from_analysis("BENEFICIARIES", st.session_state.analysis)
            st.write(beneficiaries)
        
        with col2:
            st.subheader("⚠️ Risks")
            negatives = extract_section_from_analysis("NEGATIVES / RISKS", st.session_state.analysis)
            st.write(negatives)
            
            st.subheader("Affected Groups")
            affected = extract_section_from_analysis("AFFECTED GROUPS", st.session_state.analysis)
            st.write(affected)

    with details_tab:
        st.header("Details")
        with st.expander("View Complete Analysis"):
            st.text(st.session_state.analysis)

# AI Chat Q&A
if st.session_state.analysis:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    
    user_q = st.text_input("Ask a question (e.g., 'Who proposed this bill?'):")
    
    if user_q:
        with st.spinner("Searching analysis..."):
            # Special handling for proposer questions
            if any(keyword in user_q.lower() for keyword in ["who proposed", "who sponsored", "proposer", "sponsor"]):
                patterns = [
                    r"sponsored\s+by\s+([^.]+?\.)",
                    r"introduced\s+by\s+([^.]+?\.)",
                    r"moved\s+by\s+([^.]+?\.)",
                    r"Shri\s+[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+\([^)]+\))?",
                ]
                
                proposer = None
                for pattern in patterns:
                    match = re.search(pattern, st.session_state.full_text[:2000], re.IGNORECASE)
                    if match:
                        proposer = match.group(0).strip()
                        break
                
                answer = f"**Proposer:** {proposer}" if proposer else "Proposer not specified in text."
            else:
                # Use analysis for other questions
                chat_prompt = f"""
Answer based ONLY on this analysis:

{st.session_state.analysis}

Question: {user_q}

Answer (brief, factual, bullet points if needed):
"""
                try:
                    response = llm.invoke(chat_prompt)
                    answer = response.content
                except Exception as e:
                    answer = f"Error: {e}"
            
            st.chat_message("assistant").write(answer)

# Footer
st.markdown("---")
with st.expander("ℹ️ About"):
    st.markdown("""
    **Parliament Bill Auditor**
    
    ✅ Smart validation
    ✅ Bullet-point analysis  
    ✅ Answers from analysis
    ✅ Clean 4-tab interface
    
    **How to use:**
    1. Upload parliamentary bill PDF
    2. System validates it
    3. Click green analysis button
    4. View in 4 tabs
    5. Ask questions in chat
    """)

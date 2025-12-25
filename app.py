import streamlit as st
from pypdf import PdfReader
import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from langchain_groq import ChatGroq

# ==================== FUNCTION DEFINITIONS ====================

# ========== KEEPING FIRST CODE'S EXCELLENT VALIDATION ==========
BILL_KEYWORDS = [
    "bill", "act", "parliament", "lok sabha", "rajya sabha", "gazette", 
    "legislative", "enacted", "minister", "ministry", "objects and reasons",
    "vidheyak", "adhiniyam", "purasthapit", "introduced", "passed",
    "government", "legislation", "proposed", "sponsored", "amendment"
]

REAL_BILL_PATTERNS = [
    r"a\s+bill\s+to\s+",  # "A Bill to regulate..."
    r"bill\s+no\.?\s*\d+",  # "Bill No. 123"
    r"as\s+passed\s+by\s+(lok|rajya)\s+sabha",  # "As passed by Lok Sabha"
    r"introduced\s+in\s+(lok|rajya)\s+sabha",  # "Introduced in Rajya Sabha"
    r"minister\s+of\s+",  # "Minister of Finance"
    r"sponsored\s+by",  # "Sponsored by Shri/Mr./Dr."
    r"statement\s+of\s+objects\s+and\s+reasons",  # Standard bill section
    r"financial\s+memorandum",  # Standard bill section
]

EXAMPLE_PATTERNS = [
    r"example\s+bill",
    r"test\s+document",
    r"sample\s+text",
    r"for\s+demonstration\s+purposes",
    r"carriage\s+of\s+goods",
    r"question\s*:.*answer\s*:",  # Q&A format
]

def is_valid_government_doc(text):
    """
    EXCELLENT VALIDATION from first code - distinguishes real bills from examples
    Returns: (is_valid, reason_message, bill_type)
    """
    text_lower = text.lower()
    
    if len(text.strip()) < 500:
        return False, "Document too short (less than 500 characters)", "invalid"
    
    # Check for example/test documents FIRST
    for pattern in EXAMPLE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, "This appears to be an example/test document, not an actual parliamentary bill", "example"
    
    # Check for Q&A format
    if re.search(r"question\s*:.*answer\s*:", text_lower, re.IGNORECASE | re.DOTALL):
        return False, "Document appears to contain instructional Q&A format, not a bill", "example"
    
    # Check for strong indicators of real bills
    strong_indicators = 0
    for pattern in REAL_BILL_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            strong_indicators += 1
    
    # Check for keywords
    keyword_count = sum(1 for k in BILL_KEYWORDS if k in text_lower)
    
    # Determine bill type
    bill_type = "unknown"
    if "lok sabha" in text_lower or "rajya sabha" in text_lower:
        bill_type = "indian"
        strong_indicators += 2
    
    # Validation logic
    if strong_indicators >= 2 and keyword_count >= 5:
        return True, f"✅ Valid parliamentary bill detected", bill_type
    elif strong_indicators >= 1 and keyword_count >= 3:
        return True, f"⚠️ Possible bill detected", bill_type
    else:
        return False, f"Document doesn't appear to be a parliamentary bill", "invalid"

def extract_bill_proposer(text):
    """Extract bill proposer/sponsor information"""
    patterns = [
        r"sponsored\s+by\s+([^.]+?\.)",
        r"introduced\s+by\s+([^.]+?\.)",
        r"moved\s+by\s+([^.]+?\.)",
        r"Shri\s+[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+\([^)]+\))?",
        r"Dr\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",
        r"Mr\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    return None

# ========== USING SECOND CODE'S BETTER EXTRACTION ==========
def extract_section(section_name, analysis_text):
    """Improved section extraction from second code"""
    if not analysis_text or not section_name:
        return "No analysis available."
    
    # Define section headers
    section_headers = {
        "SECTOR": "SECTOR:",
        "OBJECTIVE": "OBJECTIVE:",
        "DETAILED SUMMARY": "DETAILED SUMMARY:",
        "IMPACT ANALYSIS": "IMPACT ANALYSIS:",
        "BENEFICIARIES": "BENEFICIARIES:",
        "AFFECTED GROUPS": "AFFECTED GROUPS:",
        "POSITIVES": "POSITIVES:",
        "NEGATIVES / RISKS": "NEGATIVES / RISKS:"
    }
    
    header = section_headers.get(section_name.upper())
    if not header:
        return f"Section '{section_name}' not found."
    
    # Find the header
    header_start = analysis_text.find(header)
    if header_start == -1:
        # Try variations
        for variation in [header, header.replace(":", ""), header.upper(), header.lower()]:
            header_start = analysis_text.find(variation)
            if header_start != -1:
                header = variation
                break
        
        if header_start == -1:
            return f"Section '{section_name}' not found in analysis."
    
    # Start after header
    content_start = header_start + len(header)
    content_end = len(analysis_text)
    
    # Find next section
    all_headers = list(section_headers.values())
    for next_header in all_headers:
        if next_header == header:
            continue
        next_pos = analysis_text.find(next_header, content_start)
        if next_pos != -1 and next_pos < content_end:
            content_end = next_pos
            break
    
    # Extract content
    content = analysis_text[content_start:content_end].strip()
    
    # Clean up
    for h in all_headers:
        if h in content:
            content = content.split(h)[0].strip()
    
    return content if content else "No content for this section."

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
if "bill_proposer" not in st.session_state: 
    st.session_state.bill_proposer = None
if "bill_type" not in st.session_state: 
    st.session_state.bill_type = None
if "raw_analysis" not in st.session_state: 
    st.session_state.raw_analysis = ""

# File upload
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.raw_analysis = ""
        st.session_state.validation_status = None
        st.session_state.bill_proposer = None
        
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
        
        # Validate document (USING FIRST CODE'S VALIDATION)
        is_valid, message, bill_type = is_valid_government_doc(raw_text)
        st.session_state.validation_status = (is_valid, message)
        st.session_state.bill_type = bill_type
        
        # Extract proposer
        if is_valid and bill_type != "example":
            proposer = extract_bill_proposer(raw_text[:5000])
            if proposer:
                st.session_state.bill_proposer = proposer
    
    # Display validation status
    if st.session_state.validation_status:
        is_valid, message = st.session_state.validation_status
        
        if not is_valid:
            st.error(f"❌ {message}")
            st.warning("""
            **Please upload an actual parliamentary bill. Real bills usually contain:**
            - "A BILL TO..." at the beginning
            - Bill number (e.g., Bill No. 123 of 2024)
            - Mentions of "Lok Sabha" or "Rajya Sabha"
            - "Statement of Objects and Reasons" section
            - Sponsor/Minister name
            - Date of introduction
            """)
            
            # Option to force analysis
            with st.expander("⚠️ Force analysis anyway (for testing)"):
                force_analyze = st.checkbox("I understand this may not be a real bill, proceed anyway")
                if not force_analyze:
                    st.stop()
        else:
            st.success(f"✅ {message}")

    # Check API key
    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY environment variable.")
        st.stop()

    # Initialize LLM
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile", 
        temperature=0.1, 
        max_tokens=3500
    )

    # Generate Analysis Button - USING SECOND CODE'S BETTER BUTTON
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 GENERATE ANALYSIS", type="primary", use_container_width=True):
            with st.spinner("Analyzing document... This may take a moment."):
                # USING SECOND CODE'S BETTER PROMPT FORMAT
                prompt = f"""
You are a Policy Analyst. Analyze this parliamentary bill for students.

IMPORTANT: Use EXACTLY these section headers and format:

SECTOR:
- [One sector only: Agriculture, Finance, Education, Healthcare, Technology, Environment, Defence, Transport, etc.]

OBJECTIVE:
- [Bullet point 1]
- [Bullet point 2]
- [Bullet point 3]
- [Bullet point 4]

DETAILED SUMMARY:
- [Key provision 1]
- [Key provision 2]
- [Key provision 3]
- [Key provision 4]
- [Key provision 5]
- [Key provision 6]
- [Key provision 7]
- [Key provision 8]
- [Key provision 9]
- [Key provision 10]

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

Now analyze this bill text:

{st.session_state.full_text[:12000]}
"""
                try:
                    response = llm.invoke(prompt)
                    st.session_state.raw_analysis = response.content
                    st.session_state.analysis = response.content
                    st.success("✅ Analysis complete! View results in tabs below.")
                except Exception as e:
                    st.error(f"Analysis error: {str(e)}")

# ========== USING SECOND CODE'S BETTER TAB DISPLAY ==========
if st.session_state.analysis:
    st.markdown("---")
    
    # Create tabs (SECOND CODE'S SIMPLE TAB NAMES)
    sector_tab, summary_tab, impact_tab, details_tab = st.tabs(["Sector", "Summary", "Impact", "Details"])

    with sector_tab:
        st.header("Sector")
        sector_content = extract_section("SECTOR", st.session_state.raw_analysis)
        
        if sector_content and "not found" not in sector_content.lower() and len(sector_content) > 5:
            # Format as bullet points
            lines = sector_content.strip().split('\n')
            for line in lines:
                if line.strip():
                    if line.strip().startswith('-'):
                        st.write(line)
                    else:
                        st.write(f"- {line}")
        else:
            st.info("No sector information extracted.")

    with summary_tab:
        st.header("Summary")
        
        # Objective section
        st.subheader("Objective")
        objective_content = extract_section("OBJECTIVE", st.session_state.raw_analysis)
        
        if objective_content and "not found" not in objective_content.lower() and len(objective_content) > 10:
            lines = objective_content.strip().split('\n')
            for line in lines:
                if line.strip():
                    if line.strip().startswith('-'):
                        st.write(line)
                    else:
                        st.write(f"- {line}")
        else:
            st.info("Could not extract objective section.")
        
        # Detailed Summary section
        st.subheader("Detailed Summary")
        summary_content = extract_section("DETAILED SUMMARY", st.session_state.raw_analysis)
        
        if summary_content and "not found" not in summary_content.lower() and len(summary_content) > 20:
            lines = summary_content.strip().split('\n')
            for line in lines:
                if line.strip():
                    if line.strip().startswith('-'):
                        st.write(line)
                    else:
                        st.write(f"- {line}")
            
            # Download button
            if st.button("📥 Download Summary as PDF", key="download_summary"):
                pdf_text = f"Bill Analysis Summary\n\nObjective:\n{objective_content}\n\nDetailed Summary:\n{summary_content}"
                pdf_buffer = generate_pdf(pdf_text)
                st.download_button(
                    label="⬇️ Click to Download PDF",
                    data=pdf_buffer,
                    file_name="Bill_Summary.pdf",
                    mime="application/pdf",
                    key="pdf_download"
                )
        else:
            st.info("Could not extract detailed summary.")

    with impact_tab:
        st.header("Impact Analysis")
        
        impact_content = extract_section("IMPACT ANALYSIS", st.session_state.raw_analysis)
        
        if impact_content and "not found" not in impact_content.lower() and len(impact_content) > 20:
            st.write(impact_content)
        else:
            st.info("Could not extract impact analysis.")
        
        # Two-column layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("✅ Positives")
            positives_content = extract_section("POSITIVES", st.session_state.raw_analysis)
            if positives_content and "not found" not in positives_content.lower():
                lines = positives_content.strip().split('\n')
                for line in lines:
                    if line.strip():
                        st.write(f"• {line.strip().lstrip('-').strip()}")
            else:
                st.info("No positives listed.")
            
            st.subheader("Beneficiaries")
            beneficiaries_content = extract_section("BENEFICIARIES", st.session_state.raw_analysis)
            if beneficiaries_content and "not found" not in beneficiaries_content.lower():
                lines = beneficiaries_content.strip().split('\n')
                for line in lines:
                    if line.strip():
                        st.write(f"• {line.strip().lstrip('-').strip()}")
            else:
                st.info("No beneficiaries listed.")
        
        with col2:
            st.subheader("⚠️ Risks")
            negatives_content = extract_section("NEGATIVES / RISKS", st.session_state.raw_analysis)
            if negatives_content and "not found" not in negatives_content.lower():
                lines = negatives_content.strip().split('\n')
                for line in lines:
                    if line.strip():
                        st.write(f"• {line.strip().lstrip('-').strip()}")
            else:
                st.info("No risks listed.")
            
            st.subheader("Affected Groups")
            affected_content = extract_section("AFFECTED GROUPS", st.session_state.raw_analysis)
            if affected_content and "not found" not in affected_content.lower():
                lines = affected_content.strip().split('\n')
                for line in lines:
                    if line.strip():
                        st.write(f"• {line.strip().lstrip('-').strip()}")
            else:
                st.info("No affected groups listed.")

    with details_tab:
        st.header("Details")
        
        # Show the complete raw analysis
        st.subheader("Complete AI Analysis")
        st.text_area("Full Analysis", st.session_state.raw_analysis, height=400, key="full_analysis", disabled=True)
        
        # Show proposer if found
        if st.session_state.bill_proposer:
            st.subheader("Bill Proposer")
            st.info(f"**Detected Proposer:** {st.session_state.bill_proposer}")

# ========== USING SECOND CODE'S BETTER AI CHAT ==========
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    
    user_q = st.text_input("Ask a question about the bill:", placeholder="e.g., Who proposed this bill? What are the key provisions?")
    
    if user_q:
        with st.spinner("Searching analysis..."):
            # Special handling for proposer questions
            if any(keyword in user_q.lower() for keyword in ["who proposed", "who sponsored", "proposer", "sponsor"]):
                if st.session_state.bill_proposer:
                    answer = f"**Based on the bill text:**\n\n{st.session_state.bill_proposer}"
                else:
                    answer = "Proposer/sponsor information not found in the bill text."
            else:
                # Use the analysis for other questions
                chat_prompt = f"""
Answer the question based ONLY on this bill analysis:

{st.session_state.raw_analysis}

Question: {user_q}

Provide a clear, concise answer. If the information is not in the analysis, say so.
"""
                try:
                    response = llm.invoke(chat_prompt)
                    answer = response.content
                except Exception as e:
                    answer = f"Error generating answer: {str(e)}"
            
            st.chat_message("assistant").write(answer)

# Footer
st.markdown("---")
st.markdown("""
**Parliament Bill Auditor** - Combined Best Version  
✅ Excellent validation (from first code)  
✅ Better AI analysis & tabs (from second code)  
✅ Bullet-point formatting  
✅ Clean 4-tab interface

**How to use:**
1. Upload a parliamentary bill PDF
2. System validates it using smart detection
3. Click the green **GENERATE ANALYSIS** button
4. View results in 4 simple tabs
5. Ask specific questions in the chat
""")

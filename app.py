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

# ---------------- ENHANCED VALIDATION ----------------
BILL_KEYWORDS = [
    "bill", "act", "parliament", "lok sabha", "rajya sabha", "gazette", 
    "legislative", "enacted", "minister", "ministry", "objects and reasons",
    "vidheyak", "adhiniyam", "purasthapit", "introduced", "passed",
    "government", "legislation", "proposed", "sponsored", "amendment"
]

# Patterns that indicate REAL parliamentary bills
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

# ---------------- HELPER FUNCTIONS ----------------
def is_valid_government_doc(text):
    """
    Enhanced validation to distinguish real parliamentary bills from examples
    Returns: (is_valid, reason_message)
    """
    text_lower = text.lower()
    
    # Basic checks
    if len(text.strip()) < 500:
        return False, "Document too short (less than 500 characters)"
    
    # Check for strong indicators of real bills
    strong_indicators = 0
    for pattern in REAL_BILL_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            strong_indicators += 1
    
    # Check for keywords
    keyword_count = sum(1 for k in BILL_KEYWORDS if k in text_lower)
    
    # Validation logic
    if strong_indicators >= 2 and keyword_count >= 5:
        return True, "✅ Valid parliamentary bill detected"
    elif strong_indicators >= 1 and keyword_count >= 3:
        return True, "⚠️ Possible bill detected - proceeding with analysis"
    else:
        return False, f"❌ Document doesn't appear to be a parliamentary bill"

def format_as_bullets(text):
    """Format text as bullet points"""
    if not text:
        return ""
    
    lines = text.strip().split('\n')
    bullet_lines = []
    
    for line in lines:
        line = line.strip()
        if line:
            # If line doesn't already start with bullet, add it
            if not line.startswith('-'):
                bullet_lines.append(f"- {line}")
            else:
                bullet_lines.append(line)
    
    return '\n'.join(bullet_lines)

def parse_analysis_data(analysis_text):
    """Parse the analysis text into structured data"""
    if not analysis_text:
        return {}
    
    sections = {}
    
    # Define all section headers
    headers = [
        "SECTOR:", "OBJECTIVE:", "DETAILED SUMMARY:", "IMPACT ANALYSIS:",
        "BENEFICIARIES:", "AFFECTED GROUPS:", "POSITIVES:", "NEGATIVES / RISKS:"
    ]
    
    # Parse each section
    for i in range(len(headers)):
        header = headers[i]
        start_idx = analysis_text.find(header)
        
        if start_idx != -1:
            start_idx += len(header)
            # Find the end (next header or end of text)
            end_idx = len(analysis_text)
            for j in range(i + 1, len(headers)):
                next_header_pos = analysis_text.find(headers[j], start_idx)
                if next_header_pos != -1 and next_header_pos < end_idx:
                    end_idx = next_header_pos
                    break
            
            section_text = analysis_text[start_idx:end_idx].strip()
            # Store the section with its header as key
            section_key = header.replace(":", "").lower().replace(" ", "_")
            sections[section_key] = format_as_bullets(section_text)
    
    return sections

def extract_section(section_name):
    """Extract section from analysis data"""
    if not st.session_state.get('analysis_data'):
        return "Analysis not yet generated."
    
    # Convert section name to match our keys
    section_key = section_name.lower().replace(" ", "_")
    
    return st.session_state.analysis_data.get(section_key, "Section not found in analysis.")

def generate_pdf(text):
    """Generate PDF from text"""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    pdf.setFont("Helvetica", 10)
    
    lines = text.split("\n")
    for line in lines:
        if y < 50: 
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica", 10)
        
        # Handle bullet points
        if line.startswith('-'):
            pdf.drawString(60, y, "• " + line[1:].strip())
        else:
            pdf.drawString(50, y, line)
        y -= 15
    
    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- SESSION STATE ----------------
if "analysis" not in st.session_state: 
    st.session_state.analysis = None
if "full_text" not in st.session_state: 
    st.session_state.full_text = ""
if "last_file" not in st.session_state: 
    st.session_state.last_file = None
if "validation_status" not in st.session_state: 
    st.session_state.validation_status = None
if "analysis_data" not in st.session_state:  # Store parsed analysis data
    st.session_state.analysis_data = {}

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.validation_status = None
        st.session_state.analysis_data = {}
        
        # Extract text
        reader = PdfReader(uploaded_file)
        raw_text = ""
        for page in reader.pages:
            try:
                t = page.extract_text()
                if t: 
                    raw_text += t + "\n"
            except: 
                pass
        
        st.session_state.full_text = raw_text
        
        # Validate document
        is_valid, message = is_valid_government_doc(raw_text)
        st.session_state.validation_status = (is_valid, message)
    
    # Display validation status
    if st.session_state.validation_status:
        is_valid, message = st.session_state.validation_status
        
        if not is_valid:
            st.error(f"{message}")
            st.warning("""
            **Please upload an actual parliamentary bill. Real bills usually contain:**
            - "A BILL TO..." at the beginning
            - Bill number (e.g., Bill No. 123 of 2024)
            - Mentions of "Lok Sabha" or "Rajya Sabha"
            - "Statement of Objects and Reasons" section
            """)
            st.stop()
        else:
            st.success(f"{message}")

    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY environment variable.")
        st.stop()

    # Initialize LLM
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile", 
        temperature=0.1, 
        max_tokens=3500
    )

    # GREEN Generate Analysis Button
    if st.button("🔍 Generate Analysis", type="primary"):
        with st.spinner("Analyzing document..."):
            prompt = f"""
SYSTEM: You are a professional Policy Analyst specializing in Indian parliamentary bills.

TASK: Analyze this parliamentary bill for 8th grade students. Use ONLY the text provided.

CRITICAL FORMATTING INSTRUCTIONS:
1. Use ONLY the headings provided below
2. Each section should be bullet points (use - at the beginning of each point)
3. Keep bullet points concise (1-2 lines each)
4. No markdown formatting (no ** or #)
5. Keep language simple and clear

ANALYSIS SECTIONS (USE THESE EXACT HEADINGS):

SECTOR:
- [One sector: Agriculture, Finance, Education, Healthcare, Technology, Environment, Defence, Transport, etc.]

OBJECTIVE:
- [Bullet point 1]
- [Bullet point 2]
- [Bullet point 3]
- [Bullet point 4]

DETAILED SUMMARY:
- [Bullet point 1 - Key provision]
- [Bullet point 2 - Key provision]
- [Bullet point 3 - Key provision]
- [Continue with 10-15 key provisions]

IMPACT ANALYSIS:
Citizens:
- [Impact on citizens 1]
- [Impact on citizens 2]
- [Impact on citizens 3]

Businesses:
- [Impact on businesses 1]
- [Impact on businesses 2]
- [Impact on businesses 3]

Government:
- [Impact on government 1]
- [Impact on government 2]
- [Impact on government 3]

BENEFICIARIES:
- [Beneficiary group 1]
- [Beneficiary group 2]
- [Beneficiary group 3]
- [Beneficiary group 4]

AFFECTED GROUPS:
- [Affected group 1]
- [Affected group 2]
- [Affected group 3]
- [Affected group 4]

POSITIVES:
- [Positive aspect 1]
- [Positive aspect 2]
- [Positive aspect 3]
- [Positive aspect 4]

NEGATIVES / RISKS:
- [Risk/Negative 1]
- [Risk/Negative 2]
- [Risk/Negative 3]
- [Risk/Negative 4]

TEXT TO ANALYZE:
{st.session_state.full_text[:15000]}
"""
            try:
                response = llm.invoke(prompt)
                st.session_state.analysis = response.content
                
                # Parse the analysis into structured data
                st.session_state.analysis_data = parse_analysis_data(response.content)
                
            except Exception as e:
                st.error(f"Error during analysis: {e}")

# ---------------- UI DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    
    # Create tabs as requested
    sector_tab, summary_tab, impact_tab, details_tab = st.tabs(["Sector", "Summary", "Impact", "Details"])

    with sector_tab:
        st.header("Sector")
        sector_content = extract_section("SECTOR")
        st.write(sector_content)
        
        # Optional: Add a small visual indicator
        if "not found" not in sector_content:
            st.caption(f"📊 Primary sector identified")

    with summary_tab:
        st.header("Summary")
        
        st.subheader("Objective")
        objective_content = extract_section("OBJECTIVE")
        st.write(objective_content)
        
        st.subheader("Detailed Summary")
        detail_content = extract_section("DETAILED_SUMMARY")
        st.write(detail_content)
        
        # Download button
        if "not found" not in detail_content:
            summary_text = f"Objective:\n{objective_content}\n\nDetailed Summary:\n{detail_content}"
            pdf_buffer = generate_pdf(summary_text)
            st.download_button(
                label="⬇️ Download PDF Summary",
                data=pdf_buffer,
                file_name="Bill_Summary.pdf",
                mime="application/pdf"
            )

    with impact_tab:
        st.header("Impact Analysis")
        
        impact_content = extract_section("IMPACT_ANALYSIS")
        if impact_content != "Section not found in analysis.":
            st.write(impact_content)
        else:
            st.info("No impact analysis available")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("✅ Positives")
            positives_content = extract_section("POSITIVES")
            st.write(positives_content)
            
            st.subheader("Beneficiaries")
            beneficiaries_content = extract_section("BENEFICIARIES")
            st.write(beneficiaries_content)
        
        with col2:
            st.subheader("⚠️ Risks")
            negatives_content = extract_section("NEGATIVES_RISKS")
            st.write(negatives_content)
            
            st.subheader("Affected Groups")
            affected_content = extract_section("AFFECTED_GROUPS")
            st.write(affected_content)

    with details_tab:
        st.header("Details")
        
        # Show raw analysis in an expander
        with st.expander("View Complete Analysis"):
            st.text(st.session_state.analysis)
        
        # Show file info
        with st.expander("Document Information"):
            st.write(f"**File:** {st.session_state.last_file}")
            st.write(f"**Text length:** {len(st.session_state.full_text)} characters")
            
            # Extract and show bill name if available
            bill_match = re.search(r'([A-Z][a-z\s]+)(?:Bill|Act)[,\s]*(\d{4})', st.session_state.full_text[:500])
            if bill_match:
                st.write(f"**Bill Name:** {bill_match.group(1).strip()} {bill_match.group(2)}")

# ---------------- SMART AI CHAT (ANSWERS FROM ANALYSIS) ----------------
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    
    user_q = st.text_input("Ask a question about the bill (e.g., 'Who proposed this bill?'):")
    
    if user_q:
        with st.spinner("Finding answer in analysis..."):
            # Special handling for "who proposed" questions
            if "who proposed" in user_q.lower() or "who sponsored" in user_q.lower() or "proposer" in user_q.lower():
                # Extract proposer from original text
                proposer_patterns = [
                    r"sponsored\s+by\s+([^.]+?\.)",
                    r"introduced\s+by\s+([^.]+?\.)",
                    r"moved\s+by\s+([^.]+?\.)",
                    r"Shri\s+[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+\([^)]+\))?",
                    r"Minister\s+of\s+State\s+[^.]+?,\s+([^,]+?)\s+\(",
                    r"Shri\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s+\([^)]+\)",
                ]
                
                proposer = None
                for pattern in proposer_patterns:
                    match = re.search(pattern, st.session_state.full_text[:2000], re.IGNORECASE)
                    if match:
                        proposer = match.group(0).strip()
                        break
                
                if proposer:
                    answer = f"Based on the bill text, this bill appears to have been proposed/sponsored by:\n\n**{proposer}**"
                else:
                    answer = "The bill proposer/sponsor is not explicitly mentioned in the extracted text."
            else:
                # For other questions, build context from analysis data
                if st.session_state.analysis_data:
                    context = ""
                    for section, content in st.session_state.analysis_data.items():
                        context += f"\n\n{section.upper()}:\n{content}"
                    
                    chat_prompt = f"""
SYSTEM: You are a helpful assistant answering questions about a parliamentary bill analysis.
Answer based ONLY on the analysis provided below.
Keep answers concise and in simple language.
Use bullet points if the answer has multiple points.

BILL ANALYSIS CONTEXT:
{context}

USER QUESTION: {user_q}

ANSWER (be brief and factual):
"""
                    try:
                        response = llm.invoke(chat_prompt)
                        answer = response.content
                    except Exception as e:
                        answer = f"Error generating answer: {e}"
                else:
                    answer = "No analysis data available. Please generate analysis first."
            
            # Display answer
            st.chat_message("assistant").write(answer)

# ---------------- FOOTER ----------------
st.markdown("---")
with st.expander("ℹ️ About this tool"):
    st.markdown("""
    **Parliament Bill Auditor**
    
    This tool analyzes parliamentary bills with:
    
    ✅ **Smart Validation** - Identifies real parliamentary bills
    ✅ **Bullet-point Analysis** - Clear, concise breakdown
    ✅ **Efficient Q&A** - Answers from pre-generated analysis
    ✅ **Clean UI** - Simple, focused interface
    
    **How it works:**
    1. Upload a parliamentary bill PDF
    2. System validates it's a real bill
    3. Click "Generate Analysis" (green button)
    4. View results in four tabs
    5. Ask questions in the chat
    
    **Note:** The AI answers questions using the generated analysis, not re-reading the entire document.
    """)

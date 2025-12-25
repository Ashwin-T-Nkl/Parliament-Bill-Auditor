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

# Patterns that indicate EXAMPLE/TEST documents
EXAMPLE_PATTERNS = [
    r"example\s+bill",
    r"test\s+document",
    r"sample\s+text",
    r"for\s+demonstration\s+purposes",
    r"carriage\s+of\s+goods",  # Your specific example
    r"question\s*:.*answer\s*:",  # Q&A format like in your example
]

def is_valid_government_doc(text):
    """
    Enhanced validation to distinguish real parliamentary bills from examples
    Returns: (is_valid, reason_message, bill_type)
    """
    text_lower = text.lower()
    
    # Basic checks
    if len(text.strip()) < 500:
        return False, "Document too short (less than 500 characters)", "invalid"
    
    # Check for example/test documents FIRST
    for pattern in EXAMPLE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False, "This appears to be an example/test document, not an actual parliamentary bill", "example"
    
    # Check for Q&A format (like in your problematic example)
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
    
    # Check for specific Indian Parliament formatting
    if "lok sabha" in text_lower or "rajya sabha" in text_lower:
        bill_type = "indian"
        strong_indicators += 2  # Weight these heavily
    
    # Validation logic
    if strong_indicators >= 2 and keyword_count >= 5:
        return True, f"✅ Valid parliamentary bill detected ({strong_indicators} strong indicators, {keyword_count} keywords)", bill_type
    elif strong_indicators >= 1 and keyword_count >= 3:
        return True, f"⚠️ Possible bill detected - proceeding with analysis", bill_type
    else:
        return False, f"Document doesn't appear to be a parliamentary bill (only {keyword_count} keywords, {strong_indicators} strong indicators)", "invalid"

def extract_bill_proposer(text):
    """
    Try to extract bill proposer/sponsor information
    """
    patterns = [
        r"sponsored\s+by\s+([^.]+?\.)",  # "Sponsored by Shri XYZ."
        r"introduced\s+by\s+([^.]+?\.)",  # "Introduced by Dr. ABC."
        r"minister\s+(?:of\s+)?[^,]+?,\s+([^,]+?)\s+\(minister",  # "Minister of X, Name (Minister"
        r"mr\.\s+[^,]+?(?:\s+mp)?",  # "Mr. Name MP"
        r"shri\s+[^,]+?(?:\s+mp)?",  # "Shri Name MP"
        r"dr\.\s+[^,]+?(?:\s+mp)?",  # "Dr. Name MP"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    return None

# ---------------- SESSION STATE ----------------
if "analysis" not in st.session_state: 
    st.session_state.analysis = None
if "full_text" not in st.session_state: 
    st.session_state.full_text = ""
if "last_file" not in st.session_state: 
    st.session_state.last_file = None
if "bill_proposer" not in st.session_state: 
    st.session_state.bill_proposer = None
if "bill_type" not in st.session_state: 
    st.session_state.bill_type = None
if "validation_status" not in st.session_state: 
    st.session_state.validation_status = None

# ---------------- FILE UPLOAD ----------------
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.bill_proposer = None
        st.session_state.validation_status = None
        
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
        is_valid, message, bill_type = is_valid_government_doc(raw_text)
        st.session_state.validation_status = (is_valid, message)
        st.session_state.bill_type = bill_type
        
        # Extract proposer if possible
        if is_valid and bill_type != "example":
            proposer = extract_bill_proposer(raw_text[:5000])  # Check first 5000 chars
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
            
            # Option to force analysis anyway (for testing)
            with st.expander("⚠️ Force analysis anyway (for testing)"):
                force_analyze = st.checkbox("I understand this may not be a real bill, proceed anyway")
                if not force_analyze:
                    st.stop()
        else:
            st.success(f"✅ {message}")
            
            # Show extracted proposer if found
            if st.session_state.bill_proposer:
                st.info(f"**Bill Sponsor Detected:** {st.session_state.bill_proposer}")

    if "GROQ_API_KEY" not in os.environ:
        st.error("Please set GROQ_API_KEY environment variable.")
        st.stop()

    # Initialize LLM
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile", 
        temperature=0.1, 
        max_tokens=3500
    )

    if st.button("🔍 Generate Analysis", type="primary"):
        with st.spinner("Analyzing document..."):
            # Enhanced prompt with document type awareness
            prompt = f"""
SYSTEM: You are a professional Policy Analyst specializing in Indian parliamentary bills.

DOCUMENT TYPE CHECK: 
Based on the text, determine if this is:
1. ACTUAL PARLIAMENTARY BILL - Analyze normally
2. EXAMPLE/TEST DOCUMENT - Indicate it's an example
3. OTHER DOCUMENT - Explain what it appears to be

TASK: If this is a real bill, analyze it for 8th grade students. Use ONLY the text provided.

CRITICAL INSTRUCTIONS:
1. If the text contains instructional Q&A (like "Question: ... Answer: ..."), state this is likely example text
2. If it mentions generic acts like "Carriage of Goods by Sea Act" without parliamentary context, it's likely an example
3. Only provide bill analysis for documents mentioning Parliament, Lok Sabha, Rajya Sabha, or similar legislative bodies

FORMAT: Use these exact headings. No markdown symbols.

DOCUMENT TYPE:
[Actual Bill / Example Document / Other]

REASON:
[Brief explanation of classification]

{'='*50 if 'Actual Bill' in 'DOCUMENT TYPE:' else ''}

IF ACTUAL BILL, CONTINUE WITH:

SECTOR:
[One word: Agriculture, Finance, Education, Healthcare, Technology, Environment, Defence, Transport, etc.]

PROPOSER/SPONSOR:
[Name if found in text, otherwise "Not specified in text"]

OBJECTIVE:
[3-5 short lines]

DETAILED SUMMARY:
[10-20 bullet points]

IMPACT ANALYSIS:
Citizens:
- Bullet points
Businesses:
- Bullet points
Government:
- Bullet points

BENEFICIARIES:
- Bullet points

AFFECTED GROUPS:
- Bullet points

POSITIVES:
- Bullet points

NEGATIVES / RISKS:
- Bullet points

IF EXAMPLE/OTHER DOCUMENT:
[Explain why this appears to be example/instructional text and what it demonstrates]

TEXT:
{st.session_state.full_text[:18000]}
"""
            try:
                response = llm.invoke(prompt)
                st.session_state.analysis = response.content
            except Exception as e:
                st.error(f"Error during analysis: {e}")

# ---------------- EXTRACTION HELPER ----------------
def extract_section(title):
    """Extract section from analysis text"""
    content = st.session_state.analysis
    if not content: 
        return "No analysis available."
    
    try:
        # Find the section
        start_idx = content.find(title)
        if start_idx == -1:
            return "Section not found in analysis."
        
        # Find end of section (next major heading or end of text)
        headings = ["DOCUMENT TYPE:", "REASON:", "SECTOR:", "PROPOSER/SPONSOR:", "OBJECTIVE:", 
                   "DETAILED SUMMARY:", "IMPACT ANALYSIS:", "BENEFICIARIES:", 
                   "AFFECTED GROUPS:", "POSITIVES:", "NEGATIVES / RISKS:"]
        
        start_idx += len(title)
        end_idx = len(content)
        
        for heading in headings:
            next_heading = content.find(heading, start_idx + 1)
            if next_heading != -1 and next_heading < end_idx:
                end_idx = next_heading
        
        section_text = content[start_idx:end_idx].strip()
        
        # Clean up
        section_text = re.sub(r'^\s*[-*]\s*', '', section_text, flags=re.MULTILINE)
        section_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', section_text)
        
        return section_text if section_text else "No content in this section."
    except Exception as e:
        return f"Error extracting section: {e}"

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
        
        # Handle long lines
        if len(line) > 95:
            chunks = [line[i:i+95] for i in range(0, len(line), 95)]
            for chunk in chunks:
                pdf.drawString(50, y, chunk)
                y -= 15
        else:
            pdf.drawString(50, y, line)
            y -= 15
    
    pdf.save()
    buffer.seek(0)
    return buffer

# ---------------- UI DISPLAY ----------------
if st.session_state.analysis:
    st.markdown("---")
    
    # First check document type
    doc_type = extract_section("DOCUMENT TYPE:")
    reason = extract_section("REASON:")
    
    if "example" in doc_type.lower() or "example" in reason.lower():
        st.warning("📝 **Document Classification Result**")
        st.write(f"**Type:** {doc_type}")
        st.write(f"**Reason:** {reason}")
        st.info("""
        This appears to be example or instructional text rather than an actual parliamentary bill.
        Real parliamentary bills typically include:
        - Bill number and year
        - Specific minister/sponsor name
        - "Statement of Objects and Reasons"
        - References to Lok Sabha/Rajya Sabha
        - Date of introduction
        """)
    else:
        # Display analysis for actual bills
        st.success("✅ **Valid Parliamentary Bill Analysis**")
        
        tab1, tab2, tab3, tab4 = st.tabs(["🏷️ Overview", "📄 Summary", "📊 Impact", "🔍 Details"])

        with tab1:
            st.header("🏷️ Bill Overview")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Sector")
                sector = extract_section("SECTOR:")
                st.info(sector if sector != "Section not found in analysis." else "Not specified")
            
            with col2:
                st.subheader("Proposer/Sponsor")
                proposer = extract_section("PROPOSER/SPONSOR:")
                if proposer and proposer != "Section not found in analysis.":
                    st.info(proposer)
                elif st.session_state.bill_proposer:
                    st.info(st.session_state.bill_proposer)
                else:
                    st.info("Not specified in document")
            
            st.subheader("Document Classification")
            st.write(f"**Type:** {doc_type}")
            st.write(f"**Assessment:** {reason}")

        with tab2:
            st.header("📄 Bill Summary")
            
            st.subheader("🎯 Objective")
            objective = extract_section("OBJECTIVE:")
            st.write(objective if objective != "Section not found in analysis." else "No objective specified")
            
            st.subheader("💡 Key Provisions")
            detail = extract_section("DETAILED SUMMARY:")
            st.write(detail if detail != "Section not found in analysis." else "No detailed summary available")
            
            # Download button
            if detail and detail != "Section not found in analysis.":
                pdf_buffer = generate_pdf(f"Bill Summary\n\nObjective:\n{objective}\n\nKey Provisions:\n{detail}")
                st.download_button(
                    label="⬇️ Download PDF Summary",
                    data=pdf_buffer,
                    file_name="Bill_Summary.pdf",
                    mime="application/pdf"
                )

        with tab3:
            st.header("📊 Impact Analysis")
            
            impact = extract_section("IMPACT ANALYSIS:")
            if impact != "Section not found in analysis.":
                st.write(impact)
            else:
                st.info("No impact analysis available")
            
            col1, col2 = st.columns(2)
            with col1:
                st.success("✅ **Positives**")
                positives = extract_section("POSITIVES:")
                st.write(positives if positives != "Section not found in analysis." else "No positives listed")
                
                st.subheader("Beneficiaries")
                beneficiaries = extract_section("BENEFICIARIES:")
                st.write(beneficiaries if beneficiaries != "Section not found in analysis." else "Not specified")
            
            with col2:
                st.error("⚠️ **Risks & Concerns**")
                negatives = extract_section("NEGATIVES / RISKS:")
                st.write(negatives if negatives != "Section not found in analysis." else "No risks identified")
                
                st.subheader("Affected Groups")
                affected = extract_section("AFFECTED GROUPS:")
                st.write(affected if affected != "Section not found in analysis." else "Not specified")

        with tab4:
            st.header("🔍 Raw Analysis")
            with st.expander("View complete AI analysis"):
                st.text(st.session_state.analysis)

# ---------------- ENHANCED AI CHAT ----------------
if st.session_state.analysis and st.session_state.full_text:
    st.markdown("---")
    st.header("💬 Ask AI about this Document")
    
    # Context-aware chat
    doc_type = extract_section("DOCUMENT TYPE:")
    is_example = "example" in doc_type.lower() if doc_type else False
    
    if is_example:
        st.warning("Note: You're asking questions about an example/instructional document, not an actual parliamentary bill.")
    
    user_q = st.text_input("Ask a specific question about the document:")
    
    if user_q:
        with st.spinner("Analyzing question..."):
            # Enhanced context prompt
            chat_prompt = f"""
SYSTEM: You are a Public Policy Analyst.

CONTEXT AWARENESS:
1. Document Type: {doc_type}
2. Is Example: {is_example}

CRITICAL RULES:
1. If this is an EXAMPLE/INSTRUCTIONAL document:
   - Clearly state this at the beginning
   - Explain it's not an actual parliamentary bill
   - Answer questions about its content as demonstration material
   
2. If this is an ACTUAL PARLIAMENTARY BILL:
   - Answer based ONLY on the provided text
   - If information isn't in text, say "Not specified in the document"
   - For "who proposed", check for sponsor/minister mentions

3. For ALL documents:
   - Keep answers simple and educational
   - Be honest about limitations
   - Don't invent information

SPECIAL HANDLING FOR "WHO PROPOSED":
- Check text for: "sponsored by", "introduced by", "minister", "Shri", "Dr.", "Mr."
- If not found: "The proposer is not specified in this document excerpt"
- If it's an example: "This is an example document, so there is no actual proposer"

DOCUMENT CONTEXT (first 2000 chars):
{st.session_state.full_text[:2000]}

FULL DOCUMENT TYPE ANALYSIS:
{doc_type}
{extract_section("REASON:")}

USER QUESTION:
{user_q}

ANSWER (start with document type if example):
"""
            try:
                ans = llm.invoke(chat_prompt)
                
                # Display with appropriate styling
                if is_example:
                    with st.chat_message("assistant"):
                        st.warning("📝 **Example Document Note**")
                        st.write("This is an instructional/example document, not an actual parliamentary bill.")
                        st.write(ans.content)
                else:
                    st.chat_message("assistant").write(ans.content)
                    
            except Exception as e:
                st.error(f"Error generating answer: {e}")

# ---------------- FOOTER ----------------
st.markdown("---")
with st.expander("ℹ️ About this tool"):
    st.markdown("""
    **Parliament Bill Auditor**
    
    This tool analyzes parliamentary bills with:
    
    ✅ **Smart Validation** - Distinguishes real bills from examples
    ✅ **Proposer Detection** - Attempts to identify bill sponsors
    ✅ **Impact Analysis** - Comprehensive stakeholder analysis
    ✅ **Q&A System** - Context-aware document questioning
    
    **Upload a real parliamentary bill to get started!**
    """)

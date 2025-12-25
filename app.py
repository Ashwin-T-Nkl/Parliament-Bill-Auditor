import streamlit as st
from pypdf import PdfReader
import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from langchain_groq import ChatGroq

# ==================== FUNCTION DEFINITIONS ====================

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
        "minister", "ministry", "government", "legislation", "amendment"
    ]
    
    strong_indicators = sum(1 for pattern in REAL_BILL_PATTERNS if re.search(pattern, text_lower, re.IGNORECASE))
    keyword_count = sum(1 for k in BILL_KEYWORDS if k in text_lower)
    
    if strong_indicators >= 2 and keyword_count >= 5:
        return True, "✅ Valid parliamentary bill detected"
    elif strong_indicators >= 1 and keyword_count >= 3:
        return True, "⚠️ Possible bill detected"
    else:
        return False, "❌ Not a valid parliamentary bill"

def extract_section(section_name, analysis_text):
    """Improved section extraction that actually works"""
    if not analysis_text or not section_name:
        return "No analysis available."
    
    # Define section headers exactly as they appear in the prompt
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
    
    # Get the exact header for the requested section
    header = section_headers.get(section_name.upper())
    if not header:
        return f"Section '{section_name}' not found in headers."
    
    # Find the header in the text
    header_start = analysis_text.find(header)
    if header_start == -1:
        # Try alternative search
        header_variations = [header, header.replace(":", ""), header.upper(), header.lower()]
        for variation in header_variations:
            header_start = analysis_text.find(variation)
            if header_start != -1:
                header = variation
                break
        
        if header_start == -1:
            return f"Header '{header}' not found in analysis text."
    
    # Start after the header
    content_start = header_start + len(header)
    
    # Find where this section ends (next header or end of text)
    content_end = len(analysis_text)
    
    # Look for the next header after this one
    all_headers = list(section_headers.values())
    current_index = all_headers.index(section_headers[section_name.upper()])
    
    # Check all subsequent headers
    for next_header in all_headers[current_index + 1:]:
        next_pos = analysis_text.find(next_header, content_start)
        if next_pos != -1 and next_pos < content_end:
            content_end = next_pos
            break
    
    # Extract and clean the content
    content = analysis_text[content_start:content_end].strip()
    
    # Remove any trailing headers that might have been caught
    for h in all_headers:
        if h in content:
            content = content.split(h)[0].strip()
    
    # If content is empty or very short, try a simpler approach
    if len(content) < 10:
        # Try splitting by lines and looking for bullet points
        lines = analysis_text.split('\n')
        in_section = False
        section_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith(header):
                in_section = True
                continue
            elif in_section:
                # Check if we hit another section header
                if any(line_stripped.startswith(h) for h in all_headers if h != header):
                    break
                if line_stripped:
                    section_lines.append(line_stripped)
        
        content = '\n'.join(section_lines)
    
    return content if content else "No content found for this section."

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
        if len(line) > 100:
            chunks = [line[i:i+100] for i in range(0, len(line), 100)]
            for chunk in chunks:
                pdf.drawString(50, y, chunk)
                y -= 15
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
if "raw_analysis" not in st.session_state:  # Store raw AI response
    st.session_state.raw_analysis = ""

# File upload
uploaded_file = st.file_uploader("Upload Bill PDF", type=["pdf"])

if uploaded_file:
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.last_file = uploaded_file.name
        st.session_state.analysis = None
        st.session_state.raw_analysis = ""
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

    # Generate Analysis Button - MAKE IT PROMINENT
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 GENERATE ANALYSIS", type="primary", use_container_width=True):
            with st.spinner("Analyzing document... This may take a moment."):
                prompt = f"""
You are a Policy Analyst. Analyze this parliamentary bill for students.

IMPORTANT: Use EXACTLY these section headers and format:

SECTOR:
- [One sector only]

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
                    st.session_state.analysis = response.content  # Store for display
                    st.success("✅ Analysis complete! View results in tabs below.")
                except Exception as e:
                    st.error(f"Analysis error: {str(e)}")

# Display Analysis if available
if st.session_state.analysis:
    st.markdown("---")
    
    # Debug: Show raw analysis in expander
    with st.expander("🔧 DEBUG: View Raw AI Response", expanded=False):
        st.text_area("Raw Analysis Output", st.session_state.raw_analysis, height=300)
    
    # Create tabs
    sector_tab, summary_tab, impact_tab, details_tab = st.tabs(["📊 Sector", "📄 Summary", "📈 Impact", "🔍 Details"])

    with sector_tab:
        st.header("Sector Analysis")
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
            st.info("No sector information extracted. The AI might not have followed the format correctly.")
            # Try to extract sector from raw analysis
            if "SECTOR:" in st.session_state.raw_analysis:
                sector_part = st.session_state.raw_analysis.split("SECTOR:")[1]
                if "OBJECTIVE:" in sector_part:
                    sector_part = sector_part.split("OBJECTIVE:")[0]
                st.write(sector_part.strip())

    with summary_tab:
        st.header("Bill Summary")
        
        # Objective section
        st.subheader("🎯 Objective")
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
        st.subheader("📋 Detailed Summary")
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
        
        # Two-column layout for Positives/Risks
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
            
            st.subheader("👥 Beneficiaries")
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
            
            st.subheader("📋 Affected Groups")
            affected_content = extract_section("AFFECTED GROUPS", st.session_state.raw_analysis)
            if affected_content and "not found" not in affected_content.lower():
                lines = affected_content.strip().split('\n')
                for line in lines:
                    if line.strip():
                        st.write(f"• {line.strip().lstrip('-').strip()}")
            else:
                st.info("No affected groups listed.")

    with details_tab:
        st.header("Detailed Analysis")
        
        # Show the complete raw analysis
        st.subheader("Complete AI Analysis")
        st.text_area("Full Analysis", st.session_state.raw_analysis, height=400, key="full_analysis")
        
        # Show some stats
        st.subheader("Analysis Information")
        st.write(f"**Analysis length:** {len(st.session_state.raw_analysis)} characters")
        st.write(f"**Bill text length:** {len(st.session_state.full_text)} characters")
        st.write(f"**File:** {st.session_state.last_file}")

# AI Chat Q&A
if st.session_state.analysis and st.session_state.raw_analysis:
    st.markdown("---")
    st.header("💬 Ask AI about this Bill")
    
    user_q = st.text_input("Ask a question about the bill:", placeholder="e.g., Who proposed this bill? What are the key provisions?")
    
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
                
                answer = f"**Based on the bill text:**\n\n{proposer}" if proposer else "Proposer/sponsor information not found in the bill text."
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
**Parliament Bill Auditor** v2.0  
✅ Smart validation | ✅ Bullet-point analysis | ✅ Answers from analysis | ✅ Clean 4-tab interface

**How to use:**
1. Upload a parliamentary bill PDF
2. System validates it automatically
3. Click the green **GENERATE ANALYSIS** button
4. View results in the 4 tabs
5. Ask specific questions in the chat

**Note:** The analysis quality depends on the bill text clarity and AI response formatting.
""")

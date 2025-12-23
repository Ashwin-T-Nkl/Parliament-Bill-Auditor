import streamlit as st
from pypdf import PdfReader
import os
import re
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Parliament Bill Auditor", layout="wide")
st.title("🏛️ Parliament Bill Auditor")

# ---------------- SESSION STATE ----------------
for key in ["analysis", "view", "last_file", "full_text"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "full_text" else ""

# ---------------- UTILITIES ----------------
def clean_text(text):
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\*", "", text)
    return text.strip()

def extract_section(title, text):
    pattern = rf"{title}\s*(.*?)(?:\n[A-Z /()]+?:|\Z)"
    match = re.search(pattern, text, re.S)
    return clean_text(match.group(1)) if match else "Not available"

def is_government_bill(text):
    indicators = [
        "bill", "be it enacted", "st

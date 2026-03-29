import streamlit as st
from langchain_groq import ChatGroq
import smtplib
from email.message import EmailMessage
import re
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import pytesseract
from PIL import Image
import os

# ---------------------------
# Load ENV
# ---------------------------
load_dotenv()

# ---------------------------
# Initialize LLM
# ---------------------------
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except:
        st.error("❌ GROQ API KEY not found")
        st.stop()

llm = ChatGroq(
    model="qwen/qwen3-32b",
    temperature=0,
    api_key=api_key,
)

# ---------------------------
# Helpers
# ---------------------------

def valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email)


def extract_pdf_text(file):
    text = ""
    try:
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
    except:
        pass
    return text


def extract_image_text(file):
    try:
        img = Image.open(file)
        return pytesseract.image_to_string(img)
    except:
        return ""


def send_email(sender_email, sender_password, recipient, subject, body, attachments=None):

    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    if attachments:
        for file in attachments:
            file_data = file.getvalue()
            file_name = file.name

            if file.type == "application/pdf":
                maintype, subtype = "application", "pdf"
            elif file.type.startswith("image"):
                maintype, subtype = "image", file.type.split("/")[-1]
            else:
                maintype, subtype = "application", "octet-stream"

            msg.add_attachment(
                file_data,
                maintype=maintype,
                subtype=subtype,
                filename=file_name
            )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return "✅ Email sent successfully!"
    except Exception as e:
        return f"❌ Failed: {str(e)}"


# ---------------------------
# UI
# ---------------------------

st.set_page_config(page_title="MailGPT - AI Email Agent", page_icon="📧")

st.title("📧 MailGPT - Your AI Email Assistant")

st.info("""
🔐 Important: Gmail App Password Required

This app will NOT work with your normal Gmail password.
Use App Password only.
""")

# ---------------------------
# Form
# ---------------------------

with st.form("email_form"):

    sender_email = st.text_input("Sender Email")
    sender_password = st.text_input("App Password", type="password")
    recipient = st.text_input("Recipient Email")

    purpose = st.text_area("What is the email about?")

    # 📄 PDF Context
    st.markdown("### 📄 Context (Optional)")
    context_pdf = st.file_uploader("Upload PDF", type=["pdf"])

    # 🖼️ Image Context
    context_image = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])

    # 📎 Attachments
    st.markdown("### 📎 Attachments (Optional)")
    attachments = st.file_uploader(
        "Upload files",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True
    )

    submit = st.form_submit_button("Generate Email")

# ---------------------------
# Generate Email
# ---------------------------

if submit:

    if not valid_email(sender_email) or not valid_email(recipient):
        st.error("❌ Invalid email format")

    else:
        pdf_text = extract_pdf_text(context_pdf) if context_pdf else ""
        image_text = extract_image_text(context_image) if context_image else ""

        prompt = f"""
You are a professional email assistant.

Write a clear, natural, human sounding email.

Rules:
- Do not use symbols, emojis, dashes, or bullet points
- Keep it simple and professional

User request:
{purpose}

PDF context:
{pdf_text[:1500]}

Image context:
{image_text[:1000]}

Return strictly in this format:

Subject: <subject>

Body:
<body>
"""

        try:
            with st.spinner("Generating email..."):
                response = llm.invoke(prompt)
                text = response.content
        except Exception as e:
            st.error(f"LLM Error: {str(e)}")
            st.stop()

        # Better parsing
        subject_match = re.search(r"Subject:\s*(.*)", text)
        body_match = re.search(r"Body:\s*([\s\S]*)", text)

        subject = subject_match.group(1).strip() if subject_match else "No Subject"
        body = body_match.group(1).strip() if body_match else text

        # Save state
        st.session_state.subject = subject
        st.session_state.body = body
        st.session_state.sender_email = sender_email
        st.session_state.sender_password = sender_password
        st.session_state.recipient = recipient
        st.session_state.attachments = attachments

# ---------------------------
# Show Output
# ---------------------------

if "subject" in st.session_state:

    st.subheader("📌 Subject")
    st.write(st.session_state.subject)

    st.subheader("📄 Email Body")

    edited_body = st.text_area(
        "Edit Email",
        st.session_state.body,
        height=250
    )

    if st.button("📤 Send Email"):

        result = send_email(
            st.session_state.sender_email,
            st.session_state.sender_password,
            st.session_state.recipient,
            st.session_state.subject,
            edited_body,
            st.session_state.get("attachments")
        )

        st.success(result)
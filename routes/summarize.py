from openai import OpenAI
import os
from dotenv import load_dotenv
import PyPDF2
import docx
from pptx import Presentation
import openpyxl

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# ── Text Extractors ──────────────────────────────────────────

def extract_from_pdf(path):
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        print(f"PDF error: {e}")
    return text

def extract_from_word(path):
    text = ""
    try:
        doc = docx.Document(path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        print(f"Word error: {e}")
    return text

def extract_from_pptx(path):
    text = ""
    try:
        prs = Presentation(path)
        for i, slide in enumerate(prs.slides):
            text += f"Slide {i + 1}:\n"
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    text += shape.text + "\n"
            text += "\n"
    except Exception as e:
        print(f"PPT error: {e}")
    return text

def extract_from_excel(path):
    text = ""
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        for sheet in wb.worksheets:
            text += f"Sheet: {sheet.title}\n"
            for row in sheet.iter_rows(values_only=True):
                row_text = "\t".join(str(c) for c in row if c is not None)
                if row_text.strip():
                    text += row_text + "\n"
            text += "\n"
    except Exception as e:
        print(f"Excel error: {e}")
    return text

def extract_from_txt(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"TXT error: {e}")
        return ""

# ── Router ───────────────────────────────────────────────────

def extract_text(path, filename):
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return extract_from_pdf(path)
    elif ext in ("doc", "docx"):
        return extract_from_word(path)
    elif ext in ("ppt", "pptx"):
        return extract_from_pptx(path)
    elif ext == "xlsx":
        return extract_from_excel(path)
    elif ext == "txt":
        return extract_from_txt(path)
    else:
        return ""

# ── Summarizer ───────────────────────────────────────────────

def summarize_text(text, max_tokens=500):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes documents concisely and clearly."
                },
                {
                    "role": "user",
                    "content": f"Please summarize the following document content:\n\n{text[:6000]}"
                }
            ],
            max_tokens=max_tokens,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI error: {e}")
        return "Error summarizing document."
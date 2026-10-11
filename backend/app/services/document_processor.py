import os
from typing import List, Tuple
from pypdf import PdfReader
from docx import Document as DocxDocument
from pptx import Presentation

def extract_text_from_file(file_path: str) -> str:
    """Extract raw text from PDF, DOCX, PPTX, or TXT file."""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
            
    elif ext == ".pdf":
        text_parts = []
        reader = PdfReader(file_path)
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(f"[Page {page_num + 1}]\n{page_text}")
        return "\n\n".join(text_parts)
        
    elif ext in [".docx", ".doc"]:
        doc = DocxDocument(file_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        
    elif ext in [".pptx", ".ppt"]:
        prs = Presentation(file_path)
        text_parts = []
        for slide_num, slide in enumerate(prs.slides):
            slide_texts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_texts.append(shape.text.strip())
            if slide_texts:
                text_parts.append(f"[Slide {slide_num + 1}]\n" + "\n".join(slide_texts))
        return "\n\n".join(text_parts)
        
    else:
        raise ValueError(f"Unsupported file format: {ext}")

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """Split text into overlapping chunks suitable for semantic search."""
    if not text or not text.strip():
        return []
        
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        cleaned = para.strip()
        if not cleaned:
            continue
            
        if len(current_chunk) + len(cleaned) <= chunk_size:
            current_chunk += ("\n\n" + cleaned if current_chunk else cleaned)
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If paragraph itself is larger than chunk size, slice it
            if len(cleaned) > chunk_size:
                start = 0
                while start < len(cleaned):
                    end = min(start + chunk_size, len(cleaned))
                    chunks.append(cleaned[start:end])
                    start += (chunk_size - overlap)
                current_chunk = ""
            else:
                current_chunk = cleaned
                
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks

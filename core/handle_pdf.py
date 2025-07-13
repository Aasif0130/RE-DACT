import os

import cv2
import fitz
import numpy as np
from PyPDF2 import PdfReader

from core.misc import BLACK, is_human_image


def search_replace_in_pdf(
    path: str, words: list[str], remove_picture: bool, red_file_name: str
):
    with fitz.open(path) as doc:
        for page in doc.pages():
            was_redacted = False
            for text in words:
                instances = page.search_for(text)
                for inst in instances:
                    page.add_redact_annot(inst, fill=BLACK)
                    was_redacted = True
            if remove_picture:
                for img in page.get_images(full=True):
                    xref = img[0]  # Extract the image reference number
                    base_image = doc.extract_image(xref)
                    img_bytes = base_image["image"]
                    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                    img_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                    # Check if the image is a human image (example check)
                    if len(is_human_image(img_cv)) > 0:
                        print(f"Found a human image at {xref}")
                        rect = page.get_image_rects(xref)[0]
                        rect_ = fitz.Rect(rect[0], rect[1], rect[2], rect[3])
                        page.add_redact_annot(rect_, fill=BLACK)
                        was_redacted = True
            if was_redacted:
                page.apply_redactions()

        redacted_pdf_path = os.path.join(os.path.dirname(path), red_file_name)
        doc.save(redacted_pdf_path)
    return redacted_pdf_path


def read_pdf(pdf_file: str):
    pdf_reader = PdfReader(pdf_file)
    text = "\n\n".join(page.extract_text() for page in pdf_reader.pages)
    return text
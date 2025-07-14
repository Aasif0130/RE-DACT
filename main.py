from enum import Enum
import tempfile
import os
import pandas as pd
import streamlit as st
import logging
from pydantic import BaseModel, ValidationError
from core import read_pdf, search_replace_in_pdf, read_image, search_replace_in_image
from groq import Groq
import json
import re
import zipfile
from prompt import pii_prompt
from itertools import groupby
import streamlit.components.v1 as components
import base64

logging.basicConfig(level=logging.INFO)

client = Groq(
    api_key=st.secrets["groq_api_key"],
)

st.set_page_config(
    page_title="RE-DACT",
    page_icon="🛡",
)

def is_pdf_or_image(file):
    file_ext = os.path.splitext(file.name)[1].lower()
    if file_ext == ".pdf":
        return "pdf"
    elif file_ext in [".png", ".jpg", ".jpeg"]:
        return "image"
    else:
        return None

def read_file(file, file_type):
    if file_type is None:
        raise ValueError("Invalid file type")

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(file.getvalue())
        temp_file_path = temp_file.name

    if file_type == "pdf":
        return read_pdf(temp_file_path)
    elif file_type == "image":
        return read_image(temp_file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

class IdentifierType(str, Enum):
    EMAIL = "Email"
    GOVERNMENT_ID = "Government ID Number"
    NAME = "Name"
    PHONE_NUMBER = "Phone number"
    ADDRESS = "Address"
    UNKNOWN = "Unknown"
    ENROLMENT_NO = "Enrolment No."
    FATHERS_NAME = "Father Name"
    SURNAME = "Surname"
    VID = "VID"
    DATE_OF_BIRTH = "Date of Birth"
    PLACE_OF_BIRTH = "Place of Birth"
    DATE_OF_EXPIRY = "Date of Expiry"
    DATE = "Date"
    AADHAAR_ISSUE_DATE = "Aadhaar Issue Date"
    PIN_CODE = "PIN Code"
    Place_of_Issue = "Place of Issue"
    SubDistrict="Sub District"

class Identifier(BaseModel):
    objValue: str
    objType: IdentifierType

class IdentifiersCollection(BaseModel):
    identifier: list[Identifier]

def extract_entities(text: str):
    prompt = pii_prompt

    try:
        resp = client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            model="llama-3.3-70b-versatile",
        )

        logging.info(f"API Response: {resp}")

        resp_data = resp.choices[0].message.content.strip()

        resp_data = resp_data.replace("'", '"')
        resp_data = resp_data.replace(r'\"', '"')

        try:
            parsed_data = json.loads(resp_data)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON response: {e}")
            return []

        identifiers = []
        for item in parsed_data:
            obj_value = item.get("value", "")
            obj_type = item.get("type", "Unknown")

            if obj_type == "Given Name":
                obj_type = "Name"

            if re.match(r'\d{2}/\d{2}/\d{4}', obj_value) or re.match(r'\d{4}-\d{2}-\d{2}', obj_value):
                obj_type = "Date of Birth"

            if re.match(r'^\d{4} \d{4} \d{4}$', obj_value):
                obj_type = "Government ID Number"

            if re.match(r'\d{4}', obj_value):
                obj_type = "Government ID Number"

            if obj_type in ["Name", "Phone number", "Government ID Number", "Address"]:
                parts = obj_value.split()
                for part in parts:
                    identifier = Identifier(objValue=part, objType=obj_type)
                    identifiers.append(identifier)
                    logging.debug(f"Extracted PII: {identifier}")

            else:
                identifier = Identifier(objValue=obj_value, objType=obj_type)
                identifiers.append(identifier)
                logging.debug(f"Extracted PII: {identifier}")

        return identifiers
    except Exception as e:
        st.error(f"Unexpected error occurred during API call: {e}")
        logging.error(f"Unexpected error: {e}")
        return []

def search_replace(file, words: list[str], file_name: str, remove_picture: bool):
    red_file_name, red_file_ext = file_name.rsplit(".", 1)
    red_file_name = f"{red_file_name}_redacted.{red_file_ext}"
    file_type = is_pdf_or_image(file)

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(file.getvalue())
        temp_file_path = temp_file.name

    redacted_file_path = None

    match file_type:
        case "pdf":
            redacted_file_path = search_replace_in_pdf(
                temp_file_path, words, remove_picture, red_file_name
            )
        case "image":
            redacted_file_path = search_replace_in_image(
                temp_file_path, words, remove_picture, red_file_name
            )
        case _:
            raise ValueError("Invalid file type")

    if redacted_file_path is None:
        raise ValueError("Failed to obtain a valid redacted file path.")

    return redacted_file_path

def zip_redacted_files(file_paths: list[str]) -> str:
    zip_filename = "redacted_files.zip"
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for file_path in file_paths:
            zipf.write(file_path, os.path.basename(file_path))
    return zip_filename

@st.cache_data
def get_df(uploaded_file, file_type) -> pd.DataFrame:
    try:
        res_dict = extract_entities(read_file(uploaded_file, file_type))
        arr = [{"objValue": obj.objValue, "objType": obj.objType.value} for obj in res_dict]
        return pd.DataFrame(arr)
    except Exception as e:
        st.error(f"Error while extracting identifiers: {e}")
        logging.error(f"Error while extracting identifiers: {e}")
        return pd.DataFrame()

def show_pdf_in_iframe(file_path, width=700, height=500):
    with open(file_path, "rb") as f:
        pdf_bytes = f.read()
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    pdf_display = f"""
    <iframe
        src="data:application/pdf;base64,{base64_pdf}"
        width="{width}"
        height="{height}"
        style="border: none;"
    >
    </iframe>
    """
    components.html(pdf_display, width=width, height=height)

def show_preview(file_path, small_preview=False):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        width = 300 if small_preview else 700
        height = 400 if small_preview else 500
        show_pdf_in_iframe(file_path, width=width, height=height)
    elif ext in [".png", ".jpg", ".jpeg"]:
        width = 300 if small_preview else None
        st.image(file_path, width=width)
    else:
        st.write(f"Preview not available for {ext} files.")

# ------------------ Streamlit UI ----------------------

st.title("RE-DACT🛡️")

uploaded_files = st.file_uploader(
    "Upload PDFs or Images for redaction",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

file_data_dict = {}

if uploaded_files:
    for uploaded_file in uploaded_files:
        file_type = is_pdf_or_image(uploaded_file)

        if file_type == "pdf":
            scanned_pdf = st.radio(
                f"Is this a scanned PDF? ({uploaded_file.name})",
                ("Yes", "No"),
                index=1,
                key=f"scanned_{uploaded_file.name}",
            )

            if scanned_pdf == "Yes":
                file_type = "image"
        with st.spinner(f"Extracting data from {uploaded_file.name}..."):
            df = get_df(uploaded_file, file_type)

        if not df.empty:
            file_data_dict[uploaded_file.name] = df

if file_data_dict:
    selected_file = st.selectbox("Select a file to view extracted data", options=list(file_data_dict.keys()))

    df = file_data_dict[selected_file]

    if not df.empty:
        st.subheader(f"Extracted Data for {selected_file}")
        st.dataframe(df)
    else:
        st.warning("No extracted data available for this file.")
else:
    st.info("Please upload files to extract data from.")

if file_data_dict:
    present_obj_types = set()
    for df in file_data_dict.values():
        present_obj_types.update(df["objType"].unique())

    present_obj_types = sorted(present_obj_types)  # Optional: for sorted dropdown

    data_to_redact = st.multiselect(
        "Select data types to redact",
        options=present_obj_types,
        help="Only data types found in the uploaded files are shown."
    )

    remove_picture = st.checkbox("Remove Face")

    if st.button("Redact"):
        if len(data_to_redact) == 0:
            st.error("Please choose some data to redact")
        else:
            redacted_file_paths = []
            for uploaded_file in uploaded_files:
                file_name = uploaded_file.name
                df = file_data_dict[file_name]
                df_red = df[df["objType"].isin(data_to_redact)]
                with st.spinner(f"Redacting information in {file_name}..."):
                    redacted_file_path = search_replace(
                        uploaded_file,
                        df_red["objValue"].tolist(),
                        file_name,
                        remove_picture,
                    )
                    redacted_file_paths.append(redacted_file_path)

            # Store redacted paths in session for preview buttons
            st.session_state.redaction_done = True
            st.session_state.preview_files = redacted_file_paths

if 'redaction_done' in st.session_state and st.session_state.redaction_done:
    if len(st.session_state.preview_files) == 1:
        # Single file preview button
        if st.button("Preview Redacted File"):
            st.subheader("Preview Redacted File")
            show_preview(st.session_state.preview_files[0])

        # Download button
        with open(st.session_state.preview_files[0], "rb") as f:
            st.download_button(
                label="Download Redacted File",
                data=f.read(),
                file_name=os.path.basename(st.session_state.preview_files[0]),
                mime="application/octet-stream",
            )

    elif len(st.session_state.preview_files) > 1:
        # Multiple files preview all button with expander (acting as a modal)
        with st.expander("Preview All Redacted Files"):
            # Initialize preview index if not set
            if "modal_preview_index" not in st.session_state:
                st.session_state.modal_preview_index = 0

            def prev_file():
                if st.session_state.modal_preview_index > 0:
                    st.session_state.modal_preview_index -= 1

            def next_file():
                if st.session_state.modal_preview_index < len(st.session_state.preview_files) - 1:
                    st.session_state.modal_preview_index += 1

            idx = st.session_state.modal_preview_index
            file_name = os.path.basename(st.session_state.preview_files[idx])

            st.markdown(f"### Showing file {idx + 1} of {len(st.session_state.preview_files)}: **{file_name}**")

            show_preview(st.session_state.preview_files[idx], small_preview=True)

            col1, col2, col3 = st.columns([1, 6, 1])
            with col1:
                if st.button("⬅ Previous", key="prev_btn"):
                    prev_file()
            with col3:
                if st.button("Next ➡", key="next_btn"):
                    next_file()

        # Download zip of all files
        zip_file = zip_redacted_files(st.session_state.preview_files)

        with open(zip_file, "rb") as f:
            st.download_button(
                label="Download All Redacted Files",
                data=f.read(),
                file_name=zip_file,
                mime="application/zip",
            )

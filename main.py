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

logging.basicConfig(level=logging.INFO)

client = Groq(
    api_key=st.secrets["groq_api_key"],
)

st.set_page_config(
    page_title="RedactPal",
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

class Identifier(BaseModel):
    objValue: str
    objType: IdentifierType

class IdentifiersCollection(BaseModel):
    identifier: list[Identifier]

def extract_entities(text: str):
    prompt = (
    "Without adding any comment, analyze the following text provided by the user and return a list of JSON objects. "
    "Each element in the list must be a JSON object denoting personally identifiable information (PII). Each JSON object must contain the `value` and `type` of the PII. "
    "Personally Identifiable Information (PII) is defined as information that can be used to uniquely identify a person, such as a name, email, phone number, exact address, or government-based ID. "
    "Classify each identified PII under one of the following categories: "
    "1. `Name`: If the text looks like a name (e.g., 'John Doe', 'राज कुमार', 'சிவா'). "
    "2. `Email`: If the text looks like an email address (e.g., 'john.doe@example.com'). "
    "3. `Phone number`: If the text looks like a phone number (e.g., '9876543210'). "
    "4. `Government ID Number`: If the text looks like a government-issued ID (e.g., Aadhaar number, PAN number, driver's license), "
    "    - Examples include: Aadhaar (12-digit number), PAN (ABCDE1234F), driver's license number. "
    "5. `Address`: If the text looks like an address (e.g., '123 Main Street, New York, NY, 10001', '123 लाल किला रोड, दिल्ली', 'எண் 12, மார்க்கெட் தெரு, சென்னை'). "
    "6. `Date of Birth`: If the text looks like a date of birth (e.g., '01/01/1990', 'Aadhaar Issue Date: 01-01-2015'). "
    "7. `Enrolment No.`: If the text looks like an enrollment number (e.g., 'Enrollment No. 12345'). "
    "8. `Father Name`: If the text contains 'S/O' (e.g., 'S/O John Doe'). "
    "9. `VID`: If the text looks like a VID number (e.g., 'VID 56789'). "
    "10. `Place of Issue`: If the text indicates place of issue (e.g., 'Place of Issue: New Delhi'). "
    "11. `PIN Code`: If the text looks like a PIN code (e.g., '110001'). "
    "The input text may include multiple languages like Hindi, Tamil, Bengali, Urdu, or other local languages, and you should consider them when identifying PII. "
    "Ensure that text in languages such as Hindi, Tamil, Bengali, Urdu, or any local language is also accurately processed for PII. "
    "Return the list of identified PII as JSON objects with the 'value' and 'type' fields. For example: "
    "[{'value': 'John Doe', 'type': 'Name'}, {'value': '9876543210', 'type': 'Phone number'}]."
)

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
    red_file_name, red_file_ext = file_name.split(".", 1)
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
def get_df(uploaded_file, file_type) -> list:
    try:
        res_dict = extract_entities(read_file(uploaded_file, file_type))
        arr = [dict(obj.dict()) for obj in res_dict]
        return pd.DataFrame(arr)
    except Exception as e:
        st.error(f"Error while extracting identifiers: {e}")
        logging.error(f"Error while extracting identifiers: {e}")
        return pd.DataFrame()

st.title("RedactPal")

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
    obj_types = [e.value for e in IdentifierType]

    data_to_redact = st.multiselect(
        "Select data types to redact",
        options=obj_types,
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

            if len(redacted_file_paths) == 1:
                redacted_file_path = redacted_file_paths[0]
                with open(redacted_file_path, "rb") as f:
                    st.download_button(
                        label="Download Redacted File",
                        data=f.read(),
                        file_name=os.path.basename(redacted_file_path),
                        mime="application/octet-stream",  
                    )
            else:
                zip_file = zip_redacted_files(redacted_file_paths)
                with open(zip_file, "rb") as f:
                    st.download_button(
                        label="Download All Redacted Files",
                        data=f.read(),
                        file_name=zip_file,
                        mime="application/zip",
                    )

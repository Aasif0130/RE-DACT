# prompt.py Just putting prompt here to avoid cluttering

pii_prompt=(
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
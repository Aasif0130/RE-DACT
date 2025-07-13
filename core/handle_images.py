import itertools
from operator import itemgetter
import cv2
import pytesseract
from core.misc import BLACK, is_human_image

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Mohamad Aasif\tesseract.exe'

def cluster_list(xs: list[int], tolerance: float = 0):
    if tolerance == 0 or len(xs) < 2:
        return [[x] for x in sorted(xs)]
    groups = []
    xs = list(sorted(xs))
    current_group = [xs[0]]
    last = xs[0]

    for x in xs[1:]:
        if x <= (last + tolerance):
            current_group.append(x)
        else:
            groups.append(current_group)
            current_group = [x]
        last = x

    groups.append(current_group)
    return groups


def make_cluster_dict(values, tolerance):
    clusters = cluster_list(list(set(values)), tolerance)

    nested_tuples = [
        [(val, i) for val in value_cluster] for i, value_cluster in enumerate(clusters)
    ]
    return dict(itertools.chain(*nested_tuples))


def cluster_objects(xs: list[dict], tolerance: float):
    key_fn = lambda x: (x["coordinates"][1] + x["coordinates"][3]) / 2
    values = map(key_fn, xs)
    cluster_dict = make_cluster_dict(values, tolerance)
    get_0, get_1 = itemgetter(0), itemgetter(1)
    cluster_tuples = sorted(((x, cluster_dict.get(key_fn(x))) for x in xs), key=get_1)
    grouped = itertools.groupby(cluster_tuples, key=get_1)
    return [list(map(get_0, v)) for k, v in grouped]


def get_avg_char_width(data):
    height = 1000
    sum_widths = 0.0
    cnt = 0
    for datum in data:
        height = min(height, abs(datum["coordinates"][3] - datum["coordinates"][1]))
        sum_widths += datum["coordinates"][2] - datum["coordinates"][0]
        cnt += len(datum["value"])
    return height / 2, sum_widths // cnt


def collate_line(line_chars, tolerance, add_spaces) -> str:
    coll = ""
    last_x1 = 0

    for char in sorted(line_chars, key=lambda x: x["coordinates"][0]):
        x_min, y_min, x_max, y_max = char["coordinates"]
        print(f"Word: '{char['value']}' - Coordinates: ({x_min}, {y_min}) to ({x_max}, {y_max})")
        
        coll += " "
        while last_x1 + tolerance < char["coordinates"][0] and add_spaces:
            coll += " "
            last_x1 += tolerance
        coll += char["value"]
        last_x1 = char["coordinates"][2]

    return coll[1:] if add_spaces else coll.strip()


def extract_text(data, add_spaces: bool = True):
    min_height, x_tolerance = get_avg_char_width(data["result"][0]["details"])
    doctop_clusters = cluster_objects(
        data["result"][0]["details"], tolerance=min_height
    )
    lines = (
        collate_line(line_chars, x_tolerance, add_spaces)
        for line_chars in doctop_clusters
    )
    lines = list(lines)
    min_spaces = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
    text = "\n".join(line[min_spaces:] for line in lines)
    return text


def get_ocr_result(image_file: str, languages: str = 'eng+tam+hin'):
    img = cv2.imread(image_file)
    if img is None:
        print("Error: Image not found!")
        return None

    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, lang=languages)
    
    result = []
    for i in range(len(ocr_data['text'])):
        if int(ocr_data['conf'][i]) > 0 and ocr_data['text'][i].strip() != '':
            result.append({
                'value': ocr_data['text'][i],
                'coordinates': [
                    int(ocr_data['left'][i]),
                    int(ocr_data['top'][i]),
                    int(ocr_data['left'][i] + ocr_data['width'][i]),
                    int(ocr_data['top'][i] + ocr_data['height'][i]),
                ]
            })

    return {'result': [{'details': result}]}



def is_partial_match(value, text):
    """
    Function to check if the text contains the value as a partial match.
    """
    return value.lower() in text.lower()


def search_replace_in_image(
    path: str, words: list[str], remove_picture: bool, red_file_name: str
):
    pic = cv2.imread(path)
    if pic is None:
        print("Error: Image not found!")
        return None

    ocr_result = get_ocr_result(path)

    if "result" not in ocr_result or "details" not in ocr_result["result"][0]:
        print("Error: Invalid OCR result format.")
        return None

    for word in words:
        for instance in ocr_result["result"][0]["details"]:
            if is_partial_match(instance["value"], word): 
                x_min, y_min, x_max, y_max = instance["coordinates"]

                y_min = max(0, y_min - 10)  
                y_max = max(0, y_max + 2) 
                
                x_min = max(0, x_min - 5) 
                x_max = min(pic.shape[1], x_max + 5) 

                cv2.rectangle(pic, (x_min, y_min), (x_max, y_max), BLACK, -1)
                print(f"Redacting '{word}' at ({x_min}, {y_min}) to ({x_max}, {y_max})")

                instance['value'] = '[REDACTED]'

    if remove_picture:
        for human in is_human_image(pic):
            x, y, w, h = human
            cv2.rectangle(pic, (x, y), (x + w, y + h), BLACK, -1)
            print(f"Redacting face at ({x}, {y}) to ({x + w}, {y + h})")

    cv2.imwrite(red_file_name, pic)
    print(f"Redacted image saved as {red_file_name}")

    print("Redacted OCR Text:")
    for instance in ocr_result["result"][0]["details"]:
        print(f"Word: '{instance['value']}' - Coordinates: {instance['coordinates']}")
        
    return red_file_name


def read_image(image_file: str):
    ocr_result = get_ocr_result(image_file)
    if not ocr_result.get("result"):
        print("Error: OCR result is empty.")
        return ""
    
    text = extract_text(ocr_result)
    print("Extracted Text:", text)
    return text

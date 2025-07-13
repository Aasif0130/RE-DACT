import cv2


def is_human_image(pic: cv2.typing.MatLike):
    gray = cv2.cvtColor(pic, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier("./haarcascade_frontalface_default.xml")
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    return faces


BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
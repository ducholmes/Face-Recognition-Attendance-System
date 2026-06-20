import numpy as np
import mediapipe as mp
import cv2
import onnxruntime as ort
from mediapipe.tasks.python import vision
from config import ARCFACE_MODEL_PATH, FACE_LANDMARKER_PATH, FACE_DETECTOR_PATH

print("Loading ArcFace (InsightFace) and MediaPipe...")

# Load ArcFace (InsightFace MobileFaceNet) ONNX model
ort_session = ort.InferenceSession(ARCFACE_MODEL_PATH, providers=['CPUExecutionProvider'])
input_name = ort_session.get_inputs()[0].name
output_name = ort_session.get_outputs()[0].name

'''
Sử dụng MediaPipe để phát hiện và chuẩn hóa mặt
'''
face_landmarker = None
face_detector = None
BaseOptions = mp.tasks.BaseOptions
VisionRunningMode = vision.RunningMode

# Tạo FaceLandmarker
FaceLandmarker = vision.FaceLandmarker
FaceLandmarkerOptions = vision.FaceLandmarkerOptions

landmarker_options = FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=FACE_LANDMARKER_PATH),
    running_mode=VisionRunningMode.IMAGE,
    num_faces=10,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5
)
face_landmarker = FaceLandmarker.create_from_options(landmarker_options)

# Tạo FaceDetector
FaceDetector = vision.FaceDetector
FaceDetectorOptions = vision.FaceDetectorOptions

detector_options = FaceDetectorOptions(
    base_options=BaseOptions(model_asset_path=FACE_DETECTOR_PATH),
    running_mode=VisionRunningMode.IMAGE,
    min_detection_confidence=0.5
)

face_detector = FaceDetector.create_from_options(detector_options)

# Import từ các module khác của dự án
from .object import Face, Track
from API.db.config_manager import config_manager

# Kiểm tra sự sai khác về kích thước box
def iou(boxA, boxB):
    # box: (x1, y1, x2, y2)
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter_area = inter_w * inter_h

    boxA_area = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxB_area = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    union = boxA_area + boxB_area - inter_area
    return inter_area / union if union > 0 else 0

# Thu nhỏ ảnh và chuyển đổi sang numpy array
def resize_convert(image: np.ndarray, color=True):
    if color:
        img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    h, w = img.shape[:2]
    scale = 1
    target_w = 1920
    target_h = 1080
    target_area = target_h * target_w

    # Diện tích vượt quá -> resize theo cạnh dài nhất
    if h * w > target_area: 
        scale = min(target_h / h, target_w / w)
        new_h = int(h * scale)
        new_w = int(w * scale)
        resized_image = cv2.resize(img, (new_w, new_h))
        return resized_image, scale

    # Nếu stream nhỏ hơn diện tích tối đa thì không cần scale
    return img, 1

# Hàm nhận diện khuôn mặt thời gian thực (độ chính xác thấp hơn)
def fast_detect(frame: np.ndarray):
    # Trả về list [(x, y, width, height)]
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
    faces = face_detector.detect(mp_image)

    result = []
    if faces.detections:
        for face in faces.detections:
            bbox = face.bounding_box
            x = bbox.origin_x
            y = bbox.origin_y
            w = bbox.width
            h = bbox.height
            result.append((x, y, x+w, y+h))

    return result

# Lấy landmarks sử dụng MediaPipe
def get_landmarks_mediapipe(rgb_image: np.ndarray, bbox):
    """
    Trả về 5 điểm chính: left_eye, right_eye, nose, left_mouth, right_mouth
    """
    x1, y1, x2, y2 = bbox
    face_img = rgb_image[y1:y2, x1:x2]
    
    if face_img.size == 0:
        return None
    
    h, w = face_img.shape[:2]
    
    try:          
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=face_img)
        detection_result = face_landmarker.detect(mp_image)
        
        if not detection_result.face_landmarks:
            return None
        
        landmarks = detection_result.face_landmarks[0]
        
        # MediaPipe Face Landmarks indices cho 5 điểm quan trọng
        # Left eye: 33, Right eye: 263, Nose tip: 1, Left mouth: 61, Right mouth: 291
        left_eye = landmarks[33]
        right_eye = landmarks[263]
        nose = landmarks[1]
        left_mouth = landmarks[61]
        right_mouth = landmarks[291]
        
        points = np.array([
            [int(left_eye.x * w) + x1, int(left_eye.y * h) + y1],
            [int(right_eye.x * w) + x1, int(right_eye.y * h) + y1],
            [int(nose.x * w) + x1, int(nose.y * h) + y1],
            [int(left_mouth.x * w) + x1, int(left_mouth.y * h) + y1],
            [int(right_mouth.x * w) + x1, int(right_mouth.y * h) + y1]
        ], dtype=np.float32)
        
        return points
    except Exception as e:
        print(f"Lỗi khi lấy landmarks: {e}")
        return None

# Chuẩn hóa khuôn mặt dựa trên landmarks (align face)
def align_face(image: np.ndarray, landmarks, output_size=(112, 112)):
    """
    Chuẩn hóa khuôn mặt nghiêng về góc chuẩn
    landmarks: 5 điểm [left_eye, right_eye, nose, left_mouth, right_mouth]
    """
    if output_size == (112, 112):
        # Template chuẩn của ArcFace/InsightFace cho kích thước 112x112
        template = np.array([
            [30.2946, 51.6963],
            [65.5318, 51.5014],
            [48.0252, 71.7366],
            [33.5493, 92.3655],
            [62.7299, 92.2041]
        ], dtype=np.float32)
    else:
        # Template tương đối khác (theo tỷ lệ output_size)
        template = np.array([
            [0.31, 0.35],  # left eye
            [0.69, 0.35],  # right eye
            [0.50, 0.55],  # nose
            [0.35, 0.75],  # left mouth
            [0.65, 0.75]   # right mouth
        ], dtype=np.float32)
        template *= output_size[0]
    
    # Tính toán affine transformation
    M = cv2.estimateAffinePartial2D(landmarks, template)[0]
    
    if M is None:
        # Fallback: chỉ resize
        return cv2.resize(image, output_size)
    
    # Áp dụng transformation
    aligned = cv2.warpAffine(image, M, output_size, flags=cv2.INTER_LINEAR)
    return aligned

# Chuẩn hóa ánh sáng cho khuôn mặt
def clahe_equalize(image, clip_limit=2.0, grid_size=(8, 8)):
    # Nếu ảnh màu, chỉ xử lý kênh V trong HSV
    if len(image.shape) == 3 and image.shape[2] == 3:
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        v = hsv[:, :, 2]
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
        v_eq = clahe.apply(v)
        hsv[:, :, 2] = v_eq
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

    # Ảnh xám
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
    return clahe.apply(image)

# Dùng để cắt ẢNH mặt và CHUẨN HÓA góc độ, ánh sáng
def extract_face_aligned(image: np.ndarray, face_locations: list, align=True):
    """
    Cắt và chuẩn hóa khuôn mặt
    """
    face_array = []

    for (left, top, right, bottom) in face_locations:
        face = image[top:bottom, left:right]

        # Fallback nếu không align
        if not align:
            face_array.append(cv2.resize(face, (112, 112)))
            continue

        bbox = (left, top, right, bottom)
        landmarks = get_landmarks_mediapipe(image, bbox)

        if landmarks is not None:
            aligned_face = align_face(image, landmarks, output_size=(112, 112))
            norm_face = clahe_equalize(aligned_face)
            face_array.append(norm_face)
        else:
            face_array.append(cv2.resize(face, (112, 112)))

    return face_array

# Encode face sử dụng ArcFace (InsightFace) model qua ONNX Runtime
def encode_face(extracted_face: np.ndarray):
    """
    extracted_face: RGB image đã được aligned và resize về 112x112
    """
    # Chuẩn hóa đầu vào của InsightFace ONNX: (pixel - 127.5) / 127.5
    img_data = extracted_face.astype(np.float32)
    img_data = (img_data - 127.5) / 127.5
    
    # Chuyển từ HWC (Height, Width, Channel) sang CHW
    img_data = np.transpose(img_data, (2, 0, 1))
    # Thêm chiều batch: (1, 3, 112, 112)
    img_data = np.expand_dims(img_data, axis=0)
    
    # Thực thi inference bằng ONNX Runtime
    outputs = ort_session.run([output_name], {input_name: img_data})
    embedding = outputs[0][0]
    
    # Chuẩn hóa vector đặc trưng L2
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    # Tính toán độ tin cậy dựa trên độ sắc nét của khuôn mặt
    gray = cv2.cvtColor(extracted_face, cv2.COLOR_RGB2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Normalize confidence về [0, 1]
    conf = min(1.0, laplacian_var / 500.0)
    
    return embedding, conf

# Dùng để cắt ẢNH mặt biết vị trí (legacy - giữ tương thích)
def extract_face(image: np.ndarray, face_locations: list):
    """
    Legacy function - không align, chỉ crop
    """
    return extract_face_aligned(image, face_locations, align=False)

# Hàm đóng gói phần xử lý mọi thứ khi nhận được ảnh
def model_processor(image: np.ndarray, cached_tracks: list[Track]):
    tracks = []

    # Resize + convert
    rgb, scale = resize_convert(image, color=True)

    # Phát hiện khuôn mặt
    boxes = fast_detect(rgb)  # [(x1, y1, x2, y2)]

    # Chuẩn hóa kích cỡ
    scaled_boxes = []

    if scale != 1:
        for (x1, y1, x2, y2) in boxes:
            scaled_boxes.append((
                int(x1 / scale),
                int(y1 / scale),
                int(x2 / scale),
                int(y2 / scale)
            ))
        boxes = scaled_boxes

    # Nếu không có cached → full pipeline
    if not cached_tracks:
        # Sử dụng align=True để chuẩn hóa khuôn mặt nghiêng
        faces_img = extract_face_aligned(rgb, boxes, align=True)

        for box, face_img in zip(boxes, faces_img):
            face = Face(box)
            emb, conf = encode_face(face_img)
            face.embedding = emb
            face.confidence = conf

            track = Track(face=face)
            tracks.append(track)

        return tracks

    # =========================
    # TRACKING (có cache)
    # =========================
    used = set()

    for track in cached_tracks:
        best_iou = 0
        best_idx = -1

        for i, box in enumerate(boxes):
            if i in used:
                continue

            score = iou(track.face.bbox, box)
            if score > best_iou:
                best_iou = score
                best_idx = i

        # Nếu match tốt → update
        current_iou_threshold = config_manager.get('IOU_THRESHOLD')
        if best_iou > current_iou_threshold:
            box = boxes[best_idx]
            used.add(best_idx)

            face = Face(box)

            # Cắt ảnh khuôn mặt và kiểm tra chất lượng sắc nét trước khi chạy ArcFace ONNX
            face_img_list = extract_face_aligned(rgb, [box], align=True)
            if face_img_list:
                face_img = face_img_list[0]
                
                # Tính độ tin cậy dựa trên độ sắc nét của khuôn mặt
                gray = cv2.cvtColor(face_img, cv2.COLOR_RGB2GRAY)
                laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                new_conf = min(1.0, laplacian_var / 500.0)

                # Chỉ trích xuất embedding mới nếu chưa có hoặc chất lượng ảnh tốt hơn hẳn
                if track.face.embedding is None or new_conf > track.face.confidence:
                    emb, conf = encode_face(face_img)
                    face.embedding = emb
                    face.confidence = conf
                else:
                    # Giữ nguyên đặc trưng và độ tin cậy cũ (tiết kiệm CPU)
                    face.embedding = track.face.embedding
                    face.confidence = track.face.confidence
            else:
                face.embedding = track.face.embedding
                face.confidence = track.face.confidence

            track.update(face)
            tracks.append(track)

        else:
            # không match → có thể chết
            if not track.is_dead():
                tracks.append(track)

    # =========================
    # NEW TRACK
    # =========================
    for i, box in enumerate(boxes):
        if i in used:
            continue

        face_img = extract_face_aligned(rgb, [box], align=True)[0]
        face = Face(box)
        emb, conf = encode_face(face_img)
        face.embedding = emb
        face.confidence = conf

        track = Track(face=face)
        tracks.append(track)
    return tracks
import cv2
import base64
import numpy as np
import time
from flask import Flask, request, jsonify, render_template
from datetime import datetime

# Import từ các module của bạn
from face.core import model_processor
from services.supabase_upload import upload_image
from services.websocket_client import recognize_user

application = Flask(__name__)

'''
Chạy: python run.py
Port mặc định: 5000
'''

# Global state
current_snapshot = None
current_tracks = []
detected_face_data = None

def base64_to_image(base64_string):
    """Chuyển base64 thành numpy array (OpenCV image)"""
    # Loại bỏ header "data:image/jpeg;base64,"
    if "," in base64_string:
        base64_string = base64_string.split(",")[1]
    
    img_data = base64.b64decode(base64_string)
    np_arr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img

def image_to_base64(image):
    """Chuyển OpenCV image thành base64"""
    _, buffer = cv2.imencode('.jpg', image)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{img_base64}"

def draw_bounding_boxes(frame, tracks):
    """Vẽ bounding box lên frame"""
    output = frame.copy()
    
    for track in tracks:
        x1, y1, x2, y2 = track.face.bbox
        
        # Màu xanh lá cho khuôn mặt có embedding
        if track.face.embedding is not None:
            color = (0, 255, 0)
            label = f"Track {track.track_id}"
        else:
            color = (0, 165, 255)
            label = f"Track {track.track_id}"
        
        # Vẽ bounding box
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 3)
        
        # Thông tin
        if track.face.confidence is not None:
            info = f"{label} | Conf: {track.face.confidence:.2f}"
        else:
            info = label
        
        # Background cho text
        (text_w, text_h), _ = cv2.getTextSize(info, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(output, (x1, y1 - text_h - 10), (x1 + text_w, y1), color, -1)
        cv2.putText(output, info, (x1, y1 - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    return output

def get_largest_face_with_embedding(tracks):
    """Lấy khuôn mặt lớn nhất có embedding"""
    valid_tracks = [t for t in tracks if t.face.embedding is not None]
    
    if not valid_tracks:
        return None
    
    # Tính diện tích bbox
    largest_track = max(valid_tracks, key=lambda t: (
        (t.face.bbox[2] - t.face.bbox[0]) * (t.face.bbox[3] - t.face.bbox[1])
    ))
    
    return largest_track

def extract_face_crop(frame, bbox, padding=20):
    """Cắt khuôn mặt từ frame với padding"""
    x1, y1, x2, y2 = bbox
    h, w = frame.shape[:2]
    
    # Thêm padding
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    
    return frame[y1:y2, x1:x2]

@application.route('/')
def index():
    """Trang chủ"""
    return render_template("index.html")

@application.route('/process_frame', methods=['POST'])
def process_frame():
    """
    Nhận frame từ browser, xử lý và trả về:
    - should_stop: True nếu phát hiện khuôn mặt lớn nhất có embedding
    - processed_image: Ảnh đã vẽ bounding box
    - face_data: Thông tin khuôn mặt phát hiện được
    """
    global current_snapshot, current_tracks, detected_face_data
    
    try:
        data = request.json
        image_b64 = data.get('image')
        
        if not image_b64:
            return jsonify({'error': 'No image provided'}), 400
        
        # Chuyển base64 → OpenCV image
        frame = base64_to_image(image_b64)
        
        # Xử lý với model_processor
        tracks = model_processor(frame, current_tracks)
        current_tracks = [t for t in tracks if not t.is_dead()]
        
        # Kiểm tra có khuôn mặt lớn nhất với embedding không
        largest_face = get_largest_face_with_embedding(tracks)
        
        should_stop = False
        face_info = None
        
        if largest_face:
            # Điều kiện dừng thông minh:
            # 1. Bắt buộc có thời gian ổn định tối thiểu 1.0 giây để người dùng kịp chỉnh góc mặt/tư thế.
            #    Trong 1.0 giây này, stream KHÔNG bao giờ dừng và liên tục cập nhật embedding sắc nét nhất.
            # 2. Sau 1.0 giây, nếu đạt độ sắc nét/tin cậy cao (>= 0.80) -> Dừng ngay để lock frame đẹp.
            # 3. Quá 2.0 giây (timeout) -> Dừng luôn và lấy embedding tốt nhất đã thu thập được.
            track_duration = time.time() - largest_face.init_timestamp
            is_stabilized = track_duration >= 1.0
            is_high_confidence = largest_face.face.confidence is not None and largest_face.face.confidence >= 0.80
            is_timeout = track_duration >= 2.0
            
            if (is_stabilized and is_high_confidence) or is_timeout:
                should_stop = True
                
                # Lưu snapshot và thông tin
                current_snapshot = frame.copy()
                detected_face_data = {
                    'track': largest_face,
                    'frame': frame.copy(),
                    'timestamp': time.time()
                }
                
                x1, y1, x2, y2 = largest_face.face.bbox
                face_info = {
                    'track_id': int(largest_face.track_id),
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': float(largest_face.face.confidence) if largest_face.face.confidence else None,
                    'area': int((x2 - x1) * (y2 - y1))
                }
        
        # Vẽ bounding box
        processed_frame = draw_bounding_boxes(frame, tracks)
        processed_b64 = image_to_base64(processed_frame)
        
        return jsonify({
            'should_stop': should_stop,
            'processed_image': processed_b64,
            'face_info': face_info,
            'total_tracks': int(len(tracks)) # Ép kiểu cho chắc chắn
        })
    
    except Exception as e:
        print(f"Error processing frame: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@application.route('/continue_recognition', methods=['POST'])
def continue_recognition():
    """
    Chỉ nhận diện khuôn mặt — KHÔNG upload snapshot.
    Snapshot sẽ được upload ở bước /confirm_attendance khi người dùng xác nhận.
    """

    try:
        if not detected_face_data:
            return jsonify({'error': 'No face data available'}), 400

        track = detected_face_data['track']
        timestamp = detected_face_data['timestamp']

        # Gọi recognize_user không kèm snapshot_url
        track_id, user_id, name, message = recognize_user(
            track_id=track.track_id,
            embedding=track.face.embedding,
            timestamp=timestamp,
            snapshot_url=None
        )

        return jsonify({
            'success': True,
            'track_id': track_id,
            'user_id': user_id,
            'name': name,
            'message': message,
            'snapshot_url': None   # chưa upload, sẽ upload khi confirm
        })

    except Exception as e:
        print(f"Error in continue_recognition: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@application.route('/confirm_attendance', methods=['POST'])
def confirm_attendance():
    """
    Upload snapshot lên Supabase và trả về snapshot_url.
    Được gọi từ frontend ngay trước khi POST /api/attendance/confirm.
    """
    try:
        if not detected_face_data:
            return jsonify({'error': 'No face data available'}), 400

        track = detected_face_data['track']
        frame = detected_face_data['frame']

        # Cắt khuôn mặt
        face_crop = extract_face_crop(frame, track.face.bbox)

        # Upload lên Supabase Storage
        _, buffer = cv2.imencode(".jpg", face_crop)
        response = upload_image(buffer.tobytes())
        snapshot_url = response.path

        print(f"✓ Snapshot uploaded on confirm: {snapshot_url}")

        return jsonify({
            'success': True,
            'snapshot_url': snapshot_url
        })

    except Exception as e:
        print(f"Error in confirm_attendance: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@application.route('/register_face', methods=['POST'])
def register_face():
    """
    Trích xuất embedding từ ảnh khuôn mặt
    Nhận: image (base64)
    Trả về: embedding, face_info
    """
    
    try:
        data = request.get_json(silent=True)
        
        if data is None:
            print(f"Content-Type: {request.content_type}")
            print(f"Request data: {request.data[:100] if request.data else 'Empty'}")
            return jsonify({'error': 'No JSON data received'}), 400
        
        image_b64 = data.get('image')
        
        if not image_b64:
            print("ERROR: 'image' key not found in data")
            print(f"Available keys: {list(data.keys())}")
            return jsonify({'error': 'No image provided'}), 400
                
        if "," in image_b64:
            image_b64 = image_b64.split(",")[1]

        # Chuyển base64 → OpenCV image
        frame = base64_to_image(image_b64)

        if frame is None:
            return jsonify({'error': 'Không thể giải mã ảnh từ Base64.'}), 400
                
        try:
            # Xử lý với model_processor để lấy embedding
            tracks = model_processor(frame, [])
                        
            # Lọc các track có embedding
            valid_tracks = [t for t in tracks if t.face.embedding is not None]
            
            if not valid_tracks:
                print("ERROR: No face with embedding detected")
                return jsonify({'error': 'Không phát hiện khuôn mặt trong ảnh. Vui lòng chụp rõ mặt hơn.'}), 400
            
            # Lấy khuôn mặt lớn nhất
            largest_track = max(valid_tracks, key=lambda t: (
                (t.face.bbox[2] - t.face.bbox[0]) * (t.face.bbox[3] - t.face.bbox[1])
            ))
            
            # Lấy embedding và thông tin khuôn mặt
            embedding = largest_track.face.embedding.tolist()
            x1, y1, x2, y2 = largest_track.face.bbox
            bbox = [int(x1), int(y1), int(x2), int(y2)]
            confidence = float(largest_track.face.confidence) if largest_track.face.confidence else 0.99
            
            print(f"SUCCESS: Embedding extracted (dim: {len(embedding)})")
            
        except Exception as e:
            print(f"model_processor exception: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Lỗi khi xử lý AI: {str(e)}'}), 500

        result = {
            'success': True,
            'embedding': embedding,  # Một embedding duy nhất của khuôn mặt lớn nhất
            'face_info': {
                'bbox': bbox,
                'confidence': confidence,
                'area': int((x2 - x1) * (y2 - y1))
            }
        }
        return jsonify(result)
        
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@application.route('/reset_detection', methods=['POST'])
def reset_detection():
    """
    Reset trạng thái để thao tác lại
    """
    global current_snapshot, current_tracks, detected_face_data
    
    current_snapshot = None
    current_tracks = []
    detected_face_data = None
    
    return jsonify({'success': True, 'message': 'Reset complete'})

@application.route('/stats')
def stats():
    """Thống kê"""
    return jsonify({
        'active_tracks': len(current_tracks),
        'has_snapshot': current_snapshot is not None,
        'current_time': datetime.now().strftime("%H:%M:%S %d-%m-%Y")
    })

if __name__ == '__main__':
    application.run(debug=True, host='0.0.0.0', port=5000)
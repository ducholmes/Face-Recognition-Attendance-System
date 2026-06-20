import time

class Face:
    def __init__(self, bbox: tuple[int, int, int, int], confidence=0.0):
        self.bbox = bbox
        self.embedding = None
        self.confidence = confidence

class Track:
    FACE_ID = 0
    def __init__(self, face: Face):    
        self.track_id = Track.FACE_ID
        self.face = face          # face hiện tại
        self.user_id = None       # sau khi recognize
        self.init_timestamp = time.time()
        self.last_seen = self.init_timestamp
        Track.FACE_ID += 1

    def update(self, face: Face):
        if face.embedding is not None:
            if self.face.embedding is None or face.confidence > self.face.confidence:
                self.face.embedding = face.embedding
                self.face.confidence = face.confidence

        self.face.bbox = face.bbox
        self.last_seen = time.time()

    def is_dead(self, timeout=1.0):
        return time.time() - self.last_seen > timeout
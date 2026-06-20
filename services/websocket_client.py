import websocket
import json
import numpy as np
import threading
import time
import queue
import os

ws = None
ws_lock = threading.Lock()
message_queue = queue.Queue()
track_queues = {}
track_queues_lock = threading.Lock()
keep_alive_thread = None
running = False

API_BASE = os.getenv("API_BASE_URL", "localhost:8000")

def keep_alive_listener():
    """
    Background thread that keeps the WebSocket connection alive
    and handles incoming heartbeats/messages
    """
    global ws
    
    while running:
        if ws is None or not ws.connected:
            time.sleep(1)
            continue
        
        try:
            # Receive with timeout to allow checking running flag
            ws.settimeout(5)
            msg = ws.recv()
            
            if msg:
                try:
                    data = json.loads(msg)
                    if isinstance(data, dict) and "track_id" in data:
                        tid = data["track_id"]
                        with track_queues_lock:
                            if tid not in track_queues:
                                track_queues[tid] = queue.Queue()
                            track_queues[tid].put(data)
                    else:
                        # Queue other messages (like heartbeats)
                        message_queue.put(data)
                except json.JSONDecodeError:
                    print(f"⚠️ Invalid JSON: {msg}")
        except websocket.WebSocketTimeoutException:
            # Timeout is normal, just continue
            pass
        except websocket.WebSocketConnectionClosedException:
            print("⚠️ WebSocket connection closed")
            with ws_lock:
                ws = None
            break
        except Exception as e:
            print(f"❌ Keep-alive listener error: {e}")
            time.sleep(1)


def start_keep_alive():
    """Start the keep-alive background thread"""
    global keep_alive_thread, running
    
    if keep_alive_thread is not None and keep_alive_thread.is_alive():
        return  # Already running
    
    running = True
    keep_alive_thread = threading.Thread(target=keep_alive_listener, daemon=True)
    keep_alive_thread.start()
    print("💚 Keep-alive thread started")


def stop_keep_alive():
    """Stop the keep-alive background thread"""
    global running
    running = False
    if keep_alive_thread:
        keep_alive_thread.join(timeout=2)
    print("💔 Keep-alive thread stopped")

def get_ws_connection():
    global ws
    with ws_lock:
        try:
            # Check if connection exists and is still connected
            if ws is None or not ws.connected:
                ws = websocket.create_connection(
                    f"ws://{API_BASE}/ws",
                    timeout=10,
                    ping_interval=20,  # Send ping every 20s
                    ping_timeout=5,    # Wait 5s for pong
                    origin="http://localhost"
                )
                print("✅ WebSocket connected")
                start_keep_alive()  # Start background listener
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            ws = None
    return ws

def register_user(track_id, embedding, user_info):
    """Gửi request đăng ký user mới"""
    conn = get_ws_connection()
    if not conn:
        return track_id, "Connection Error"
    
    try:
        payload = {
            "action": "register",
            "track_id": track_id,
            "embedding": embedding.tolist() if isinstance(embedding, np.ndarray) else embedding,
            "user_info": user_info
        }
        
        # Get or create specific queue for this track_id
        with track_queues_lock:
            if track_id not in track_queues:
                track_queues[track_id] = queue.Queue()
            t_queue = track_queues[track_id]
            
        # Clear any stale responses for this track
        while not t_queue.empty():
            try:
                t_queue.get_nowait()
            except queue.Empty:
                break
                
        with ws_lock:
            conn.send(json.dumps(payload))
        
        # Wait for response on our specific queue
        timeout = time.time() + 30
        
        while time.time() < timeout:
            try:
                response = t_queue.get(timeout=1)
                return response.get("track_id"), response.get("message")
            except queue.Empty:
                continue
        
        return track_id, "Response timeout"
    except Exception as e:
        print(f"❌ Register error: {e}")
        global ws
        with ws_lock:
            if ws:
                try:
                    ws.close()
                except:
                    pass
            ws = None
        return track_id, str(e)

def recognize_user(track_id, embedding, timestamp, snapshot_url):
    conn = get_ws_connection()
    if not conn:
        return track_id, None, None, "Connection Error"
    
    try:
        payload = {
            "action": "recognize",
            "track_id": track_id,
            "embedding": embedding.tolist() if isinstance(embedding, np.ndarray) else embedding,
            "snapshot_url": snapshot_url,
            "timestamp": timestamp
        }

        # Get or create specific queue for this track_id
        with track_queues_lock:
            if track_id not in track_queues:
                track_queues[track_id] = queue.Queue()
            t_queue = track_queues[track_id]
            
        # Clear any stale responses for this track
        while not t_queue.empty():
            try:
                t_queue.get_nowait()
            except queue.Empty:
                break

        with ws_lock:
            conn.send(json.dumps(payload))
        print(f"📤 Sent request: track_id={track_id}")
        
        # Wait for response on our specific queue
        timeout = time.time() + 30  # 30 second timeout
        
        while time.time() < timeout:
            try:
                resp = t_queue.get(timeout=1)
                print(f"📥 Received for track {track_id}: {resp}")
                
                # Got real response - return student_id, name, and message
                student_id = resp.get("student_id")
                name = resp.get("name")
                return resp.get("track_id"), student_id, name, "Success"
            except queue.Empty:
                continue
        
        return track_id, None, None, "Response timeout"
        
    except Exception as e:
        print(f"❌ Recognition error: {e}")
        global ws
        with ws_lock:
            if ws:
                try:
                    ws.close()
                except:
                    pass
            ws = None
        return track_id, None, None, str(e)
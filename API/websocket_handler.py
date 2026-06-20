import asyncio
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from API.services.recognition import recognize_face


async def heartbeat(websocket: WebSocket):
    """Send heartbeat to keep connection alive"""
    try:
        while True:
            await asyncio.sleep(15)
            try:
                await websocket.send_json({"type": "heartbeat"})
            except Exception as e:
                print(f"❌ Heartbeat send failed: {e}")
                break  # Exit on failure instead of looping forever
    except asyncio.CancelledError:
        print("💓 Heartbeat task cancelled")
    except Exception as e:
        print(f"❌ Heartbeat error: {e}")


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🟢 WebSocket connected")
    
    # Start heartbeat task
    heartbeat_task = asyncio.create_task(heartbeat(websocket))

    try:
        while True:

            data = await websocket.receive_json()
            print("📩 Received:", data)

            action = data.get("action")

            # =========================
            # RECOGNIZE FACE
            # =========================
            if action == "recognize":

                embedding = data.get("embedding")
                track_id = data.get("track_id")
                snapshot_url = data.get("snapshot_url")

                # -------------------------
                # validate input
                # -------------------------
                if embedding is None:
                    await websocket.send_json({
                        "track_id": track_id,
                        "error": "missing embedding"
                    })
                    continue

                # =========================
                # AI RECOGNITION (Pinecone)
                # =========================
                result = recognize_face(embedding)

                if result is None:
                    await websocket.send_json({
                        "track_id": track_id,
                        "error": "recognition failed"
                    })
                    continue

                print("🧠 Recognition result:", result)

                # =========================
                # RESPONSE TO CLIENT
                # (save_attendance được gọi sau khi người dùng xác nhận trên UI)
                # =========================
                await websocket.send_json({
                    "track_id": track_id,
                    **result
                })

            # =========================
            # REGISTER (future)
            # =========================
            elif action == "register":
                await websocket.send_json({
                    "message": "register not implemented yet"
                })

            # =========================
            # UNKNOWN ACTION
            # =========================
            else:
                await websocket.send_json({
                    "error": "unknown action",
                    "action": action
                })

    except WebSocketDisconnect:
        print("🔌 Client disconnected")
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
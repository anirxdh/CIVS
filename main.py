"""
Hand Gesture Based Voting System (HGVS)
Flask web application - main entry point
"""
import os
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, Response
)

from db import init_db, record_vote
from camera import CameraManager
from face_auth import FaceAuthSession
from gesture import GestureSession, create_gesture_recognizer, create_hand_landmarker

app = Flask(__name__)
app.secret_key = os.environ.get("HGVS_SECRET_KEY", "hgvs-dev-secret-key-change-in-prod")

# ---------------------------------------------------------------------------
# Load ML models once at startup
# ---------------------------------------------------------------------------
import tensorflow as tf
MODEL = None
GESTURE_RECOGNIZER = None
HAND_LANDMARKER = None

def load_models():
    global MODEL, GESTURE_RECOGNIZER, HAND_LANDMARKER
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.h5")
    MODEL = tf.keras.models.load_model(model_path)
    print("CNN gesture model loaded (fallback).")

    GESTURE_RECOGNIZER = create_gesture_recognizer()
    print("MediaPipe GestureRecognizer initialized (thumbs up/down).")

    HAND_LANDMARKER = create_hand_landmarker()
    print("MediaPipe HandLandmarker initialized (finger counting).")

# ---------------------------------------------------------------------------
# Global session state (one voter at a time - kiosk mode)
# ---------------------------------------------------------------------------
_camera = None
_auth_session = None
_gesture_session = None

def get_camera():
    global _camera
    if _camera is None:
        _camera = CameraManager.get_instance()
    if not _camera.is_running():
        _camera.start()
    return _camera

# ---------------------------------------------------------------------------
# Party configuration
# ---------------------------------------------------------------------------
PARTIES = {
    '1': {'name': 'BJP',      'logo': 'parties/bjp.png',      'sign': 'signs/1.png'},
    '2': {'name': 'ADMK',     'logo': 'parties/ADMK.jpeg',    'sign': 'signs/2.png'},
    '3': {'name': 'DMK',      'logo': 'parties/DMK.jpeg',     'sign': 'signs/3.png'},
    '4': {'name': 'Congress',  'logo': 'parties/congress.png', 'sign': 'signs/4.png'},
    '5': {'name': 'TDP',      'logo': 'parties/TDP.jpg',      'sign': 'signs/5.png'},
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return redirect(url_for('auth'))


@app.route('/auth')
def auth():
    global _auth_session
    camera = get_camera()
    _auth_session = FaceAuthSession(camera)
    _auth_session.start()
    return render_template('auth.html')


@app.route('/auth_status')
def auth_status():
    global _auth_session
    if _auth_session is None:
        return jsonify({"state": "idle", "message": "No authentication session active."})
    return jsonify(_auth_session.get_status())


@app.route('/auth_success', methods=['POST'])
def auth_success():
    global _auth_session
    if _auth_session and _auth_session.matched_voter:
        voter = _auth_session.matched_voter
        session["voter_id"] = voter["voter_id"]
        session["voter_name"] = voter["name"]
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "No matched voter."}), 400


@app.route('/voting')
def voting():
    if "voter_id" not in session:
        return redirect(url_for('auth'))

    global _gesture_session
    camera = get_camera()
    _gesture_session = GestureSession(camera, MODEL, GESTURE_RECOGNIZER, HAND_LANDMARKER)
    _gesture_session.start()

    return render_template(
        'voting.html',
        voter_name=session["voter_name"],
        parties=PARTIES,
    )


@app.route('/video_feed')
def video_feed():
    camera = get_camera()
    return Response(
        camera.generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
    )


@app.route('/gesture_status')
def gesture_status():
    global _gesture_session
    if _gesture_session is None:
        return jsonify({"state": "idle", "message": "No gesture session active."})
    return jsonify(_gesture_session.get_status())


@app.route('/restart_gesture', methods=['POST'])
def restart_gesture():
    global _gesture_session
    if "voter_id" not in session:
        return jsonify({"success": False}), 400
    camera = get_camera()
    _gesture_session = GestureSession(camera, MODEL, GESTURE_RECOGNIZER, HAND_LANDMARKER)
    _gesture_session.start()
    return jsonify({"success": True})


@app.route('/confirm_vote', methods=['POST'])
def confirm_vote():
    voter_id = session.get("voter_id")
    data = request.get_json()
    party = data.get("party") if data else None

    if not voter_id or not party:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    success = record_vote(voter_id, party)
    if success:
        session.clear()
        return jsonify({"success": True, "message": f"Vote recorded for {party}."})
    else:
        return jsonify({
            "success": False,
            "message": "Vote could not be recorded. You may have already voted."
        }), 409


@app.route('/vote_complete')
def vote_complete():
    return render_template('vote_complete.html')


# ===========================================================================
# AGVS (Audio Gesture Voting System) - COMMENTED OUT
# Uncomment when ready to upgrade to full CIVS
# ===========================================================================
#
# import speech_recognition as sr
#
# is_listening = False
# last_speech_result = None
#
# @app.route('/audio_voting')
# def audio_voting():
#     return render_template('audio_voting.html', parties=PARTIES)
#
# @app.route('/start_listening', methods=['POST'])
# def start_listening():
#     global is_listening
#     is_listening = True
#     def listen_thread():
#         global is_listening, last_speech_result
#         r = sr.Recognizer()
#         with sr.Microphone() as source:
#             r.adjust_for_ambient_noise(source)
#             try:
#                 audio = r.listen(source, timeout=5)
#                 text = r.recognize_google(audio).lower()
#                 last_speech_result = text
#             except Exception as e:
#                 last_speech_result = str(e)
#         is_listening = False
#     import threading
#     threading.Thread(target=listen_thread, daemon=True).start()
#     return jsonify({"status": "listening"})
#
# @app.route('/get_speech_result')
# def get_speech_result():
#     return jsonify({
#         "is_listening": is_listening,
#         "result": last_speech_result,
#     })
#

# ---------------------------------------------------------------------------
# Application startup
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    load_models()

    print("=" * 60)
    print("  Hand Gesture Based Voting System (HGVS)")
    print("  Open your browser: http://localhost:8080")
    print("=" * 60)

    app.run(
        debug=False,
        host='0.0.0.0',
        port=8080,
        threaded=True,
    )

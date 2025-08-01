import speech_recognition as sr
import numpy as np
import matplotlib.pyplot as plt
import cv2
import os
from PIL import Image
import string
from flask import Flask, render_template, request, jsonify, redirect, url_for
import threading
import time
import json

app = Flask(__name__)

# Global vote counts
vote_counts = {
    'BJP': 0,
    'ADMK': 0,
    'DMK': 0,
    'Congress': 0,
    'DMDK': 0
}

# Party information
parties = {
    '1': 'BJP',
    '2': 'ADMK', 
    '3': 'DMK',
    '4': 'Congress',
    '5': 'DMDK'
}

# Global variables for audio voting
is_listening = False
last_speech_result = None

def run(runfile):
    with open(runfile,"r") as rnf:
        exec(rnf.read())

def Next():
    run("signdetect.py")

def show_party_info():
    """Display available parties and their numbers"""
    info = "Available Political Parties:\n\n"
    for num, party in parties.items():
        info += f"{num}. {party}\n"
    info += "\nSpeak the number of the party you want to vote for."
    return info

def update_vote_count(party_name):
    """Update vote count for the selected party"""
    if party_name in vote_counts:
        vote_counts[party_name] += 1
        return True
    return False

def listen_for_vote():
    """Listen for user's vote"""
    global is_listening, last_speech_result
    
    r = sr.Recognizer()
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        try:
            audio = r.listen(source, timeout=5)
            text = r.recognize_google(audio).lower()
            last_speech_result = text
            
            # Extract number from speech
            for word in text.split():
                if word in parties:
                    party_name = parties[word]
                    if update_vote_count(party_name):
                        return f"Vote recorded for {party_name}!"
                    else:
                        return "Error recording vote."
            
            return "Could not recognize party number. Please try again."
            
        except sr.WaitTimeoutError:
            return "No speech detected. Please try again."
        except sr.UnknownValueError:
            return "Could not understand audio. Please try again."
        except Exception as e:
            return f"Error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html', parties=parties, vote_counts=vote_counts)

@app.route('/audio_voting')
def audio_voting():
    return render_template('audio_voting.html', parties=parties, vote_counts=vote_counts)

@app.route('/gesture_voting')
def gesture_voting():
    return render_template('gesture_voting.html', parties=parties, vote_counts=vote_counts)

@app.route('/start_listening', methods=['POST'])
def start_listening():
    global is_listening
    is_listening = True
    
    def listen_thread():
        global is_listening, last_speech_result
        result = listen_for_vote()
        is_listening = False
        last_speech_result = result
    
    threading.Thread(target=listen_thread, daemon=True).start()
    return jsonify({"status": "listening"})

@app.route('/get_speech_result')
def get_speech_result():
    global is_listening, last_speech_result
    return jsonify({
        "is_listening": is_listening,
        "result": last_speech_result,
        "vote_counts": vote_counts
    })

@app.route('/confirm_vote', methods=['POST'])
def confirm_vote():
    data = request.get_json()
    party_name = data.get('party')
    
    if party_name and update_vote_count(party_name):
        return jsonify({
            "success": True,
            "message": f"Vote recorded for {party_name}!",
            "vote_counts": vote_counts
        })
    else:
        return jsonify({
            "success": False,
            "message": "Error recording vote."
        })

@app.route('/start_gesture_detection')
def start_gesture_detection():
    # This would start the gesture detection system
    # For now, we'll just return success
    return jsonify({"status": "gesture_detection_started"})

def create_templates():
    """Create HTML template files"""
    
    # Main index template
    index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contact-less Integrated Voting System</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 2.5em;
        }
        .voting-options {
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin-top: 40px;
        }
        .voting-option {
            padding: 20px;
            border: 2px solid #ddd;
            border-radius: 10px;
            text-decoration: none;
            color: #333;
            text-align: center;
            font-size: 1.2em;
            font-weight: bold;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }
        .voting-option:hover {
            border-color: #667eea;
            background: #e3f2fd;
            transform: translateY(-2px);
        }
        .vote-counts {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .vote-counts h3 {
            margin-top: 0;
            color: #333;
        }
        .vote-count {
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
            padding: 5px 0;
            border-bottom: 1px solid #ddd;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🗳️ Contact-less Integrated Voting System</h1>
        
        <div class="voting-options">
            <a href="/audio_voting" class="voting-option">
                🎙️ Audio-Based Voting (AGVS)
            </a>
            <a href="/gesture_voting" class="voting-option">
                ✋ Hand Gesture-Based Voting (HGVS)
            </a>
        </div>
        
        <div class="vote-counts">
            <h3>Current Vote Counts:</h3>
            {% for party, count in vote_counts.items() %}
            <div class="vote-count">
                <span>{{ party }}:</span>
                <span>{{ count }}</span>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
    """
    
    # Audio voting template
    audio_voting_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio-Based Voting System</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
        .party-info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .party-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        .party-item {
            padding: 10px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            text-align: center;
        }
        .status {
            text-align: center;
            padding: 20px;
            margin: 20px 0;
            border-radius: 10px;
            font-weight: bold;
        }
        .listening {
            background: #e3f2fd;
            color: #1976d2;
        }
        .success {
            background: #e8f5e8;
            color: #2e7d32;
        }
        .error {
            background: #ffebee;
            color: #c62828;
        }
        .button {
            background: #667eea;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 5px;
            font-size: 1.1em;
            cursor: pointer;
            margin: 10px;
            transition: background 0.3s ease;
        }
        .button:hover {
            background: #5a6fd8;
        }
        .button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .vote-counts {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .vote-count {
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
            padding: 5px 0;
            border-bottom: 1px solid #ddd;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ Audio-Based Voting System</h1>
        
        <div class="party-info">
            <h3>Available Political Parties:</h3>
            <div class="party-list">
                {% for num, party in parties.items() %}
                <div class="party-item">
                    <strong>{{ num }}. {{ party }}</strong>
                </div>
                {% endfor %}
            </div>
            <p style="margin-top: 15px; text-align: center; font-style: italic;">
                Speak the number of the party you want to vote for.
            </p>
        </div>
        
        <div id="status" class="status">
            Click 'Start Listening' to begin voting
        </div>
        
        <div style="text-align: center;">
            <button id="listenBtn" class="button" onclick="startListening()">Start Listening</button>
            <button class="button" onclick="window.location.href='/'">Back to Menu</button>
        </div>
        
        <div class="vote-counts">
            <h3>Current Vote Counts:</h3>
            <div id="voteCounts">
                {% for party, count in vote_counts.items() %}
                <div class="vote-count">
                    <span>{{ party }}:</span>
                    <span id="count-{{ party }}">{{ count }}</span>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        let isListening = false;
        
        function startListening() {
            if (isListening) return;
            
            isListening = true;
            document.getElementById('listenBtn').disabled = true;
            document.getElementById('status').className = 'status listening';
            document.getElementById('status').textContent = 'Listening... Speak the party number clearly';
            
            fetch('/start_listening', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            }).then(() => {
                checkSpeechResult();
            });
        }
        
        function checkSpeechResult() {
            fetch('/get_speech_result')
                .then(response => response.json())
                .then(data => {
                    if (!data.is_listening && data.result) {
                        isListening = false;
                        document.getElementById('listenBtn').disabled = false;
                        
                        if (data.result.includes('Vote recorded')) {
                            document.getElementById('status').className = 'status success';
                            document.getElementById('status').textContent = data.result;
                            updateVoteCounts(data.vote_counts);
                        } else {
                            document.getElementById('status').className = 'status error';
                            document.getElementById('status').textContent = data.result;
                        }
                    } else if (data.is_listening) {
                        setTimeout(checkSpeechResult, 1000);
                    }
                });
        }
        
        function updateVoteCounts(counts) {
            for (const [party, count] of Object.entries(counts)) {
                const element = document.getElementById(`count-${party}`);
                if (element) {
                    element.textContent = count;
                }
            }
        }
    </script>
</body>
</html>
    """
    
    # Gesture voting template
    gesture_voting_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hand Gesture-Based Voting System</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
        .instructions {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        .gesture-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .gesture-item {
            padding: 15px;
            background: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
        }
        .gesture-item:hover {
            border-color: #667eea;
            background: #e3f2fd;
        }
        .status {
            text-align: center;
            padding: 20px;
            margin: 20px 0;
            border-radius: 10px;
            font-weight: bold;
        }
        .active {
            background: #e3f2fd;
            color: #1976d2;
        }
        .button {
            background: #667eea;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 5px;
            font-size: 1.1em;
            cursor: pointer;
            margin: 10px;
            transition: background 0.3s ease;
        }
        .button:hover {
            background: #5a6fd8;
        }
        .vote-counts {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        .vote-count {
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
            padding: 5px 0;
            border-bottom: 1px solid #ddd;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>✋ Hand Gesture-Based Voting System</h1>
        
        <div class="instructions">
            <h3>Hand Gesture Voting Instructions:</h3>
            <div class="gesture-list">
                <div class="gesture-item">1 finger = BJP</div>
                <div class="gesture-item">2 fingers = ADMK</div>
                <div class="gesture-item">3 fingers = DMK</div>
                <div class="gesture-item">4 fingers = Congress</div>
                <div class="gesture-item">5 fingers = DMDK</div>
            </div>
            <p style="margin-top: 15px; text-align: center; font-style: italic;">
                Show your hand gesture to the camera, then make the confirmation gesture to finalize your vote.
            </p>
        </div>
        
        <div id="status" class="status">
            Click 'Start Camera' to begin gesture voting
        </div>
        
        <div style="text-align: center;">
            <button id="cameraBtn" class="button" onclick="startCamera()">Start Camera</button>
            <button class="button" onclick="window.location.href='/'">Back to Menu</button>
        </div>
        
        <div class="vote-counts">
            <h3>Current Vote Counts:</h3>
            <div id="voteCounts">
                {% for party, count in vote_counts.items() %}
                <div class="vote-count">
                    <span>{{ party }}:</span>
                    <span id="count-{{ party }}">{{ count }}</span>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        function startCamera() {
            document.getElementById('status').className = 'status active';
            document.getElementById('status').textContent = 'Starting camera... Show your hand gesture to the camera';
            document.getElementById('cameraBtn').disabled = true;
            
            // In a real implementation, this would start the gesture detection
            // For now, we'll simulate it
            setTimeout(() => {
                document.getElementById('status').textContent = 'Camera started. Show your hand gesture in the camera window.';
            }, 2000);
        }
    </script>
</body>
</html>
    """
    
    # Write templates to files
    with open('templates/index.html', 'w') as f:
        f.write(index_html)
    
    with open('templates/audio_voting.html', 'w') as f:
        f.write(audio_voting_html)
    
    with open('templates/gesture_voting.html', 'w') as f:
        f.write(gesture_voting_html)

if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create HTML templates
    create_templates()
    
    print("Starting CIVS Web Server...")
    print("Open your browser and go to: http://localhost:8080")
    app.run(debug=True, host='0.0.0.0', port=8080)
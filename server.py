import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


from inference import OmniInference
import flask
import base64
import tempfile
import traceback
from flask import Flask, Response, stream_with_context, render_template_string, jsonify, request


# HTML template for the web interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mini-Omni Voice AI</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: white;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }
        .status {
            text-align: center;
            padding: 15px;
            margin: 20px 0;
            border-radius: 10px;
            font-weight: bold;
        }
        .status.ready {
            background: rgba(76, 175, 80, 0.3);
            border: 2px solid #4CAF50;
        }
        .status.error {
            background: rgba(244, 67, 54, 0.3);
            border: 2px solid #f44336;
        }
        .status.processing {
            background: rgba(255, 193, 7, 0.3);
            border: 2px solid #FFC107;
        }
        .controls {
            text-align: center;
            margin: 30px 0;
        }
        .record-btn {
            background: #e74c3c;
            border: none;
            color: white;
            padding: 15px 30px;
            font-size: 18px;
            border-radius: 50px;
            cursor: pointer;
            margin: 10px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        .record-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
        }
        .record-btn.recording {
            background: #c0392b;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        .text-input {
            width: 100%;
            padding: 15px;
            font-size: 16px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            margin: 20px 0;
        }
        .text-input::placeholder {
            color: rgba(255, 255, 255, 0.7);
        }
        .send-btn {
            background: #3498db;
            border: none;
            color: white;
            padding: 15px 30px;
            font-size: 16px;
            border-radius: 10px;
            cursor: pointer;
            width: 100%;
            margin: 10px 0;
            transition: all 0.3s ease;
        }
        .send-btn:hover {
            background: #2980b9;
        }
        .response {
            margin-top: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            min-height: 100px;
        }
        .audio-player {
            width: 100%;
            margin: 20px 0;
        }
        .loading {
            text-align: center;
            margin: 20px 0;
        }
        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top: 4px solid white;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .api-info {
            margin-top: 40px;
            padding: 20px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            font-family: monospace;
            font-size: 14px;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
        }
        .tab {
            flex: 1;
            padding: 15px;
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .tab.active {
            background: rgba(255, 255, 255, 0.3);
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 Mini-Omni Voice AI</h1>
        
        <div id="status" class="status ready">
            ✅ Ready for voice interaction
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('voice')">Voice Chat</button>
            <button class="tab" onclick="switchTab('text')">Text Chat</button>
            <button class="tab" onclick="switchTab('api')">API Info</button>
        </div>
        
        <!-- Voice Chat Tab -->
        <div id="voice-tab" class="tab-content active">
            <div class="controls">
                <button id="recordBtn" class="record-btn" onclick="toggleRecording()">
                    🎤 Start Recording
                </button>
                <p>Click the button above to start voice recording, then click again to stop and process.</p>
            </div>
        </div>
        
        <!-- Text Chat Tab -->
        <div id="text-tab" class="tab-content">
            <input type="text" id="textInput" class="text-input" placeholder="Type your message here..." 
                   onkeypress="if(event.key==='Enter') sendText()">
            <button class="send-btn" onclick="sendText()">Send Message</button>
            <p><em>Note: Text input will be converted to speech using TTS, then processed by the voice model.</em></p>
        </div>
        
        <!-- API Info Tab -->
        <div id="api-tab" class="tab-content">
            <div class="api-info">
                <h3>API Endpoint Information</h3>
                <p><strong>Base URL:</strong> {{ base_url }}</p>
                <p><strong>Chat Endpoint:</strong> POST /chat</p>
                <br>
                <h4>Example Usage:</h4>
                <pre>curl -X POST {{ base_url }}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "base64_encoded_wav_data",
    "stream_stride": 4,
    "max_tokens": 2048
  }'</pre>
                <br>
                <h4>Response:</h4>
                <p>Streaming audio/wav response</p>
            </div>
        </div>
        
        <div class="response">
            <h3>Response:</h3>
            <div id="loading" class="loading" style="display: none;">
                <div class="spinner"></div>
                <p>Processing your request...</p>
            </div>
            <div id="result">No response yet. Start a conversation!</div>
            <audio id="audioPlayer" class="audio-player" controls style="display: none;"></audio>
        </div>
    </div>
    
    <script>
        let isRecording = false;
        let mediaRecorder;
        let audioChunks = [];
        
        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
        }
        
        async function toggleRecording() {
            const recordBtn = document.getElementById('recordBtn');
            const status = document.getElementById('status');
            
            if (!isRecording) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];
                    
                    mediaRecorder.ondataavailable = event => {
                        audioChunks.push(event.data);
                    };
                    
                    mediaRecorder.onstop = async () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        await sendAudio(audioBlob);
                    };
                    
                    mediaRecorder.start();
                    isRecording = true;
                    recordBtn.textContent = '⏹️ Stop Recording';
                    recordBtn.classList.add('recording');
                    status.className = 'status processing';
                    status.textContent = '🎤 Recording... Click stop when finished';
                } catch (error) {
                    console.error('Error accessing microphone:', error);
                    status.className = 'status error';
                    status.textContent = '❌ Microphone access denied. Please allow microphone permissions.';
                }
            } else {
                mediaRecorder.stop();
                isRecording = false;
                recordBtn.textContent = '🎤 Start Recording';
                recordBtn.classList.remove('recording');
                status.className = 'status processing';
                status.textContent = '⏳ Processing your voice...';
                
                // Stop all tracks
                const stream = mediaRecorder.stream;
                stream.getTracks().forEach(track => track.stop());
            }
        }
        
        async function sendAudio(audioBlob) {
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            const audioPlayer = document.getElementById('audioPlayer');
            const status = document.getElementById('status');
            
            try {
                loading.style.display = 'block';
                result.textContent = 'Processing...';
                
                // Convert to base64
                const reader = new FileReader();
                reader.onloadend = async () => {
                    const base64Audio = reader.result.split(',')[1];
                    
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            audio: base64Audio,
                            stream_stride: 4,
                            max_tokens: 2048
                        })
                    });
                    
                    if (response.ok) {
                        const audioBlob = await response.blob();
                        const audioUrl = URL.createObjectURL(audioBlob);
                        audioPlayer.src = audioUrl;
                        audioPlayer.style.display = 'block';
                        audioPlayer.play();
                        
                        result.innerHTML = '🎵 <strong>Voice response generated!</strong><br>Play the audio above to hear Mini-Omni\'s response.';
                        status.className = 'status ready';
                        status.textContent = '✅ Response ready! You can record another message.';
                    } else {
                        throw new Error('Failed to process audio');
                    }
                };
                reader.readAsDataURL(audioBlob);
                
            } catch (error) {
                console.error('Error:', error);
                result.textContent = 'Error: ' + error.message;
                status.className = 'status error';
                status.textContent = '❌ Error processing request. Please try again.';
            } finally {
                loading.style.display = 'none';
            }
        }
        
        async function sendText() {
            const textInput = document.getElementById('textInput');
            const text = textInput.value.trim();
            
            if (!text) {
                alert('Please enter some text first!');
                return;
            }
            
            const status = document.getElementById('status');
            status.className = 'status processing';
            status.textContent = '⏳ Converting text to speech and processing...';
            
            // For now, show a message that text-to-speech integration is needed
            const result = document.getElementById('result');
            result.innerHTML = `
                <strong>Text Input:</strong> "${text}"<br><br>
                <em>Note: Text-to-speech integration is not implemented in this demo. 
                The Mini-Omni model requires audio input. Please use the voice recording feature above.</em>
            `;
            
            status.className = 'status ready';
            status.textContent = '✅ Ready for voice interaction';
            textInput.value = '';
        }
        
        // Check if the browser supports necessary APIs
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            document.getElementById('status').className = 'status error';
            document.getElementById('status').textContent = '❌ Your browser does not support audio recording. Please use a modern browser.';
        }
    </script>
</body>
</html>
'''


class OmniChatServer(object):
    def __init__(self, ip='0.0.0.0', port=60808, run_app=True,
                 ckpt_dir='./checkpoint', device='cuda:0') -> None:
        server = Flask(__name__)
        # CORS(server, resources=r"/*")
        # server.config["JSON_AS_ASCII"] = False

        self.client = OmniInference(ckpt_dir, device)
        self.client.warm_up()
        self.base_url = f"http://{ip}:{port}"

        # Web UI routes
        server.route("/", methods=["GET"])(self.index)
        server.route("/health", methods=["GET"])(self.health)
        
        # API routes
        server.route("/chat", methods=["POST"])(self.chat)
        server.route("/chat", methods=["GET"])(self.chat_info)

        if run_app:
            print(f"\n🌐 Mini-Omni Web UI available at: {self.base_url}")
            print(f"🔗 API endpoint: {self.base_url}/chat")
            print(f"📊 Health check: {self.base_url}/health")
            print("\n✨ Open your browser and navigate to the URL above to use the web interface!")
            server.run(host=ip, port=port, threaded=False)
        else:
            self.server = server

    def index(self):
        """Serve the main web interface."""
        return render_template_string(HTML_TEMPLATE, base_url=self.base_url)
    
    def health(self):
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "message": "Mini-Omni server is running",
            "endpoints": {
                "web_ui": "/",
                "chat_api": "/chat (POST)",
                "health": "/health"
            }
        })
    
    def chat_info(self):
        """Information about the chat endpoint when accessed via GET."""
        return jsonify({
            "error": "Method Not Allowed", 
            "message": "This endpoint requires POST method with audio data",
            "usage": {
                "method": "POST",
                "endpoint": "/chat",
                "content_type": "application/json",
                "body": {
                    "audio": "base64_encoded_wav_data",
                    "stream_stride": 4,
                    "max_tokens": 2048
                }
            },
            "web_ui": "Visit / for the web interface"
        }), 405

    def chat(self) -> Response:
        """Handle voice chat requests."""
        req_data = flask.request.get_json()
        try:
            if not req_data or "audio" not in req_data:
                return jsonify({
                    "error": "Missing audio data",
                    "message": "Please provide base64 encoded audio data in the 'audio' field"
                }), 400
                
            data_buf = req_data["audio"].encode("utf-8")
            data_buf = base64.b64decode(data_buf)
            stream_stride = req_data.get("stream_stride", 4)
            max_tokens = req_data.get("max_tokens", 2048)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(data_buf)
                audio_generator = self.client.run_AT_batch_stream(f.name, stream_stride, max_tokens)
                return Response(stream_with_context(audio_generator), mimetype="audio/wav")
                
        except Exception as e:
            print(f"Error in chat endpoint: {e}")
            print(traceback.format_exc())
            return jsonify({
                "error": "Internal server error",
                "message": str(e)
            }), 500


# CUDA_VISIBLE_DEVICES=1 gunicorn -w 2 -b 0.0.0.0:60808 'server:create_app()'
def create_app():
    server = OmniChatServer(run_app=False)
    return server.server


def serve(ip='0.0.0.0', port=60808, device='cuda:0'):
    OmniChatServer(ip, port=port, run_app=True, device=device)


if __name__ == "__main__":
    import fire
    fire.Fire(serve)
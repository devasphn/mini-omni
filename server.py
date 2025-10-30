import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from inference import OmniInference
import flask
import base64
import tempfile
import traceback
from flask import Flask, Response, stream_with_context, render_template_string, jsonify, request

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mini-Omni Voice AI</title>
<style>
/* styles omitted for brevity */
</style>
</head>
<body>
<div class="container">
  <h1>🎤 Mini-Omni Voice AI</h1>
  <div id="status" class="status ready">✅ Ready for voice interaction</div>
  <div class="tabs">
    <button class="tab active" data-tab="voice">Voice Chat</button>
    <button class="tab" data-tab="api">API Info</button>
  </div>
  <div id="voice-tab" class="tab-content active">
    <div class="controls">
      <button id="recordBtn" class="record-btn">🎤 Start Recording</button>
    </div>
  </div>
  <div id="api-tab" class="tab-content">
    <div class="api-info">
      <h3>API Endpoint Information</h3>
      <p><strong>Base URL:</strong> {{ base_url }}</p>
      <p><strong>Chat Endpoint:</strong> POST /chat</p>
      <pre>curl -X POST {{ base_url }}/chat -H "Content-Type: application/json" -d '{"audio":"base64_wav"}'</pre>
    </div>
  </div>
  <div class="response">
    <h3>Response:</h3>
    <div id="loading" class="loading" style="display:none;"><div class="spinner"></div><p>Processing...</p></div>
    <div id="result">No response yet. Start a conversation!</div>
    <audio id="audioPlayer" class="audio-player" controls style="display:none;"></audio>
  </div>
</div>
<script>
(() => {
  let isRecording = false;
  let mediaRecorder; let audioChunks = [];
  const recordBtn = document.getElementById('recordBtn');
  const statusEl = document.getElementById('status');
  const resultEl = document.getElementById('result');
  const loadingEl = document.getElementById('loading');
  const audioPlayer = document.getElementById('audioPlayer');

  // Tab handling
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab + '-tab').classList.add('active');
    });
  });

  async function sendAudioBlob(wavBlob){
    loadingEl.style.display='block';
    resultEl.textContent='Processing...';
    try{
      const arrBuf = await wavBlob.arrayBuffer();
      const b64 = btoa(String.fromCharCode(...new Uint8Array(arrBuf)));
      const res = await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({audio:b64,stream_stride:4,max_tokens:2048})});
      if(!res.ok) throw new Error('HTTP '+res.status);
      const outBlob = await res.blob();
      const url = URL.createObjectURL(outBlob);
      audioPlayer.src = url; audioPlayer.style.display='block'; audioPlayer.play();
      resultEl.innerHTML='🎵 <b>Voice response generated!</b>';
      statusEl.className='status ready'; statusEl.textContent='✅ Response ready!';
    }catch(e){
      console.error(e); resultEl.textContent='Error: '+e.message; statusEl.className='status error'; statusEl.textContent='❌ Error processing request.';
    } finally { loadingEl.style.display='none'; }
  }

  function toWavBlobFromPCM(pcmBlob){ return pcmBlob; }

  recordBtn.addEventListener('click', async () => {
    if(!isRecording){
      try{
        const stream = await navigator.mediaDevices.getUserMedia({audio:true});
        mediaRecorder = new MediaRecorder(stream, {mimeType: 'audio/webm'});
        audioChunks = [];
        mediaRecorder.ondataavailable = e => { if(e.data && e.data.size>0) audioChunks.push(e.data); };
        mediaRecorder.onstop = async () => {
          // Convert webm to wav using offline AudioContext for broader backend compatibility
          const webmBlob = new Blob(audioChunks, {type:'audio/webm'});
          const arrayBuf = await webmBlob.arrayBuffer();
          const audioCtx = new (window.OfflineAudioContext||window.webkitOfflineAudioContext)(1, 16000*5, 16000);
          try{
            const decoded = await (new AudioContext()).decodeAudioData(arrayBuf.slice(0));
            const length = Math.min(decoded.length, 16000*30);
            const offline = new OfflineAudioContext(1, length, 16000);
            const buffer = offline.createBuffer(1, length, 16000);
            decoded.copyFromChannel(buffer.getChannelData(0),0,0);
            const src = offline.createBufferSource(); src.buffer = buffer; src.connect(offline.destination); src.start();
            const rendered = await offline.startRendering();
            const wav = PCM16Wav(rendered.getChannelData(0), 16000);
            await sendAudioBlob(wav);
          }catch(err){
            // Fallback: send webm as-is (server supports temp file decoding)
            await sendAudioBlob(webmBlob);
          }
        };
        mediaRecorder.start(); isRecording=true; recordBtn.textContent='⏹️ Stop Recording'; recordBtn.classList.add('recording'); statusEl.className='status processing'; statusEl.textContent='🎤 Recording...';
      }catch(e){ statusEl.className='status error'; statusEl.textContent='❌ Mic permission denied.'; }
    } else {
      mediaRecorder.stop(); isRecording=false; recordBtn.textContent='🎤 Start Recording'; recordBtn.classList.remove('recording'); statusEl.className='status processing'; statusEl.textContent='⏳ Processing...';
      mediaRecorder.stream.getTracks().forEach(t=>t.stop());
    }
  });

  function PCM16Wav(float32Array, sampleRate){
    const buffer = new ArrayBuffer(44 + float32Array.length*2);
    const view = new DataView(buffer);
    const writeString=(o,s)=>{for(let i=0;i<s.length;i++)view.setUint8(o+i,s.charCodeAt(i));};
    const toPCM=(o,i)=>{const s=Math.max(-1,Math.min(1,float32Array[i]));view.setInt16(o, s<0?s*0x8000:s*0x7FFF, true);};
    writeString(0,'RIFF'); view.setUint32(4,36+float32Array.length*2,true); writeString(8,'WAVE'); writeString(12,'fmt ');
    view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true); view.setUint32(24,sampleRate,true); view.setUint32(28,sampleRate*2,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
    writeString(36,'data'); view.setUint32(40,float32Array.length*2,true);
    let offset=44; for(let i=0;i<float32Array.length;i++,offset+=2) toPCM(offset,i);
    return new Blob([buffer], {type:'audio/wav'});
  }
})();
</script>
</body>
</html>'''

class OmniChatServer(object):
    def __init__(self, ip='0.0.0.0', port=60808, run_app=True, ckpt_dir='./checkpoint', device='cuda:0') -> None:
        server = Flask(__name__)
        self.client = OmniInference(ckpt_dir, device)
        self.client.warm_up()
        self.base_url = f"http://{ip}:{port}"
        server.route('/', methods=['GET'])(self.index)
        server.route('/health', methods=['GET'])(self.health)
        server.route('/chat', methods=['POST'])(self.chat)
        server.route('/chat', methods=['GET'])(self.chat_info)
        if run_app:
            server.run(host=ip, port=port, threaded=False)
        else:
            self.server = server
    def index(self):
        return render_template_string(HTML_TEMPLATE, base_url=self.base_url)
    def health(self):
        return jsonify({"status":"healthy"})
    def chat_info(self):
        return jsonify({"error":"Method Not Allowed","message":"POST /chat with base64 wav"}),405
    def chat(self) -> Response:
        req_data = flask.request.get_json() or {}
        try:
            if 'audio' not in req_data:
                return jsonify({"error":"Missing 'audio' field"}),400
            data_buf = base64.b64decode(req_data['audio'].encode('utf-8'))
            stream_stride = req_data.get('stream_stride',4)
            max_tokens = req_data.get('max_tokens',2048)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(data_buf)
                audio_generator = self.client.run_AT_batch_stream(f.name, stream_stride, max_tokens)
                return Response(stream_with_context(audio_generator), mimetype='audio/wav')
        except Exception as e:
            print(traceback.format_exc())
            return jsonify({"error":"internal","message":str(e)}),500

def create_app():
    server = OmniChatServer(run_app=False)
    return server.server

def serve(ip='0.0.0.0', port=60808, device='cuda:0'):
    OmniChatServer(ip, port=port, run_app=True, device=device)

if __name__ == '__main__':
    import fire
    fire.Fire(serve)

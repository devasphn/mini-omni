import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from inference import OmniInference
import flask
import base64
import tempfile
import traceback
from flask import Flask, Response, stream_with_context, render_template_string, jsonify

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mini-Omni Voice AI</title>
<style>
body{font-family:system-ui,Arial,sans-serif;max-width:860px;margin:0 auto;padding:24px;background:#0f172a;color:#e2e8f0}
.container{background:#111827;border-radius:16px;padding:24px;border:1px solid #1f2937}
h1{margin:0 0 12px}
.status{padding:12px 14px;border-radius:10px;margin:8px 0;font-weight:600}
.status.ready{background:#063f2e;border:1px solid #10b981}
.status.processing{background:#3a2b05;border:1px solid #f59e0b}
.status.error{background:#421c1d;border:1px solid #ef4444}
.controls{text-align:center;margin:18px 0}
.record-btn{background:#ef4444;border:none;color:#fff;padding:12px 20px;border-radius:9999px;font-size:16px;cursor:pointer}
.record-btn.recording{background:#dc2626}
.audio-player{width:100%;margin-top:12px}
.loading{text-align:center}
.spinner{border:4px solid rgba(255,255,255,.2);border-top:4px solid #fff;border-radius:50%;width:36px;height:36px;margin:10px auto;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="container">
  <h1>🎤 Mini-Omni Voice AI</h1>
  <div id="status" class="status ready">✅ Ready for voice interaction</div>
  <div class="controls"><button id="recordBtn" class="record-btn">🎤 Start Recording</button></div>
  <div class="response">
    <div id="loading" class="loading" style="display:none"><div class="spinner"></div><p>Processing...</p></div>
    <div id="result">No response yet. Start a conversation!</div>
    <audio id="audioPlayer" class="audio-player" controls style="display:none"></audio>
  </div>
</div>
<script>
(()=>{
  let isRecording=false; let mediaRecorder=null; let audioChunks=[]; let audioCtx=null;
  const recordBtn=document.getElementById('recordBtn');
  const statusEl=document.getElementById('status');
  const resultEl=document.getElementById('result');
  const loadingEl=document.getElementById('loading');
  const audioPlayer=document.getElementById('audioPlayer');

  function setStatus(type,msg){ statusEl.className='status '+type; statusEl.textContent=msg; }

  async function blobToBase64(blob){
    const buf = await blob.arrayBuffer();
    // Avoid call stack via String.fromCharCode spread; use chunked conversion
    const bytes = new Uint8Array(buf);
    let binary='';
    const chunkSize = 0x8000; // 32KB
    for (let i=0;i<bytes.length;i+=chunkSize){
      const chunk = bytes.subarray(i, i+chunkSize);
      binary += String.fromCharCode.apply(null, chunk);
    }
    return btoa(binary);
  }

  async function sendAudioBlob(wavBlob){
    try{
      loadingEl.style.display='block';
      resultEl.textContent='Processing...';
      const b64 = await blobToBase64(wavBlob);
      const res = await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({audio:b64,stream_stride:4,max_tokens:2048})});
      if(!res.ok) throw new Error('HTTP '+res.status);
      const outBlob = await res.blob();
      audioPlayer.src = URL.createObjectURL(outBlob);
      audioPlayer.style.display='block';
      await audioPlayer.play().catch(()=>{});
      resultEl.innerHTML='🎵 <b>Voice response generated!</b>';
      setStatus('ready','✅ Response ready!');
    }catch(e){ console.error(e); setStatus('error','❌ Error: '+e.message); resultEl.textContent='Error: '+e.message; }
    finally{ loadingEl.style.display='none'; }
  }

  function pcm16Wav(float32Array, sampleRate){
    const length = float32Array.length;
    const buffer = new ArrayBuffer(44 + length*2);
    const view = new DataView(buffer);
    function writeStr(off,str){ for(let i=0;i<str.length;i++) view.setUint8(off+i,str.charCodeAt(i)); }
    writeStr(0,'RIFF'); view.setUint32(4,36+length*2,true); writeStr(8,'WAVE'); writeStr(12,'fmt ');
    view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true); view.setUint32(24,sampleRate,true); view.setUint32(28,sampleRate*2,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
    writeStr(36,'data'); view.setUint32(40,length*2,true);
    let offset=44;
    for(let i=0;i<length;i++,offset+=2){ const s=Math.max(-1,Math.min(1,float32Array[i])); view.setInt16(offset, s<0?s*0x8000:s*0x7FFF, true); }
    return new Blob([buffer],{type:'audio/wav'});
  }

  async function webmToWav(webmBlob){
    // Decode with an AudioContext; guard against recursive decode causing stack overflow
    try{
      if(!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const arrayBuf = await webmBlob.arrayBuffer();
      const decoded = await audioCtx.decodeAudioData(arrayBuf.slice(0));
      // Downmix to mono and resample approximately by rendering to OfflineAudioContext
      const targetRate = 16000;
      const frames = Math.min(decoded.length, targetRate * Math.ceil(decoded.duration));
      const offline = new OfflineAudioContext(1, frames, targetRate);
      const src = offline.createBufferSource();
      // Mixdown
      const mono = offline.createBuffer(1, decoded.length, decoded.sampleRate);
      const tmp = new Float32Array(decoded.length);
      decoded.copyFromChannel(tmp, 0);
      if(decoded.numberOfChannels>1){
        const tmp2 = new Float32Array(decoded.length);
        decoded.copyFromChannel(tmp2, 1);
        for(let i=0;i<tmp.length;i++) tmp[i] = 0.5*(tmp[i]+tmp2[i]);
      }
      mono.copyToChannel(tmp,0);
      src.buffer = mono; src.connect(offline.destination); src.start();
      const rendered = await offline.startRendering();
      const channel = rendered.getChannelData(0);
      return pcm16Wav(channel, targetRate);
    }catch(err){
      // Fallback: send original webm (backend writes and handles file)
      return webmBlob;
    }
  }

  recordBtn.addEventListener('click', async ()=>{
    if(!isRecording){
      try{
        const stream = await navigator.mediaDevices.getUserMedia({audio:true});
        mediaRecorder = new MediaRecorder(stream, {mimeType: 'audio/webm'});
        audioChunks = [];
        mediaRecorder.ondataavailable = (e)=>{ if(e.data && e.data.size>0) audioChunks.push(e.data); };
        mediaRecorder.onstop = async ()=>{
          const webmBlob = new Blob(audioChunks,{type:'audio/webm'});
          const wavBlob = await webmToWav(webmBlob);
          await sendAudioBlob(wavBlob);
          // cleanup
          stream.getTracks().forEach(t=>t.stop());
          mediaRecorder = null; audioChunks = [];
        };
        mediaRecorder.start(); isRecording=true; recordBtn.textContent='⏹️ Stop Recording'; recordBtn.classList.add('recording'); setStatus('processing','🎤 Recording...');
      }catch(e){ setStatus('error','❌ Mic permission denied or unsupported.'); }
    } else {
      if(mediaRecorder && mediaRecorder.state!=='inactive') mediaRecorder.stop();
      isRecording=false; recordBtn.textContent='🎤 Start Recording'; recordBtn.classList.remove('recording'); setStatus('processing','⏳ Processing...');
    }
  });
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

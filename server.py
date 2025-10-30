import sys, os, base64, tempfile, traceback
from flask import Flask, Response, stream_with_context, render_template_string, jsonify, request
from inference import OmniInference

HTML_TEMPLATE = r'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mini-Omni Voice AI</title><style>body{font-family:system-ui,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px} .card{max-width:900px;margin:0 auto;background:#111827;border:1px solid #1f2937;border-radius:16px;padding:24px} h1{margin:0 0 12px;font-size:32px} .status{padding:10px 12px;border-radius:10px;margin:10px 0;font-weight:600} .status.ready{background:#063f2e;border:1px solid #10b981} .status.processing{background:#3a2b05;border:1px solid #f59e0b} .status.error{background:#421c1d;border:1px solid #ef4444} .btn{padding:12px 18px;border-radius:9999px;border:none;cursor:pointer;color:#fff;background:#ef4444} .btn.recording{background:#dc2626} audio{width:100%;margin-top:12px}</style></head><body><div class="card"><h1>🎤 Mini-Omni Voice AI</h1><div id="status" class="status ready">✅ Ready</div><button id="rec" class="btn">🎤 Start Recording</button><div id="info" style="margin-top:12px;font-family:monospace;font-size:14px"></div><audio id="player" controls style="display:none"></audio></div><script>(()=>{const statusEl=document.getElementById('status');const btn=document.getElementById('rec');const player=document.getElementById('player');const info=document.getElementById('info');let rec=null;let chunks=[];let streaming=false;function setStatus(cls,msg){statusEl.className='status '+cls;statusEl.textContent=msg;}async function postAudio(blob){try{const b64=await (async()=>{const buf=await blob.arrayBuffer();let binary='';const bytes=new Uint8Array(buf);const step=0x8000;for(let i=0;i<bytes.length;i+=step){binary+=String.fromCharCode.apply(null,bytes.subarray(i,i+step));}return btoa(binary);})();setStatus('processing','⏳ Uploading...');const res=await fetch('/chat_stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({audio:b64})}); if(!res.ok) throw new Error('HTTP '+res.status); const reader=res.body.getReader(); const stream=new ReadableStream({start(controller){function pump(){reader.read().then(({done,value})=>{if(done){controller.close();return;}controller.enqueue(value);pump();});}}});const response=new Response(stream);const audioBlob=await response.blob(); player.src=URL.createObjectURL(audioBlob); player.style.display='block'; await player.play().catch(()=>{}); setStatus('ready','✅ Response ready!'); }catch(e){console.error(e); setStatus('error','❌ '+e.message);} } btn.addEventListener('click',async()=>{ if(!rec){ try{const stream=await navigator.mediaDevices.getUserMedia({audio:true}); rec=new MediaRecorder(stream,{mimeType:'audio/webm'}); chunks=[]; rec.ondataavailable=e=>{if(e.data&&e.data.size>0)chunks.push(e.data);}; rec.onstop=async()=>{const blob=new Blob(chunks,{type:'audio/webm'}); await postAudio(blob); stream.getTracks().forEach(t=>t.stop()); rec=null; chunks=[]; btn.textContent='🎤 Start Recording'; btn.classList.remove('recording');}; rec.start(); btn.textContent='⏹️ Stop Recording'; btn.classList.add('recording'); setStatus('processing','🎤 Recording...'); }catch(e){ setStatus('error','❌ Mic permission denied'); } } else { if(rec.state!=='inactive') rec.stop(); } });})();</script></body></html>'''

class OmniChatServer:
    def __init__(self, ip='0.0.0.0', port=60808, run_app=True, ckpt_dir='./checkpoint', device='cuda:0'):
        app = Flask(__name__)
        self.client = OmniInference(ckpt_dir, device)
        self.client.warm_up()
        self.app = app
        app.add_url_rule('/', view_func=self.index)
        app.add_url_rule('/chat_stream', methods=['POST'], view_func=self.chat_stream)
        app.add_url_rule('/health', view_func=self.health)
        if run_app:
            app.run(host=ip, port=port, threaded=False)

    def index(self):
        return render_template_string(HTML_TEMPLATE)

    def health(self):
        return jsonify({'status':'ok'})

    def chat_stream(self):
        try:
            data = request.get_json(force=True)
            if not data or 'audio' not in data:
                return jsonify({'error':'missing audio'}), 400
            raw = base64.b64decode(data['audio'].encode('utf-8'))
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
                f.write(raw)
                temp_path = f.name
            # use existing stream generator to produce audio frames (wav)
            gen = self.client.run_AT_batch_stream(temp_path)
            def generate():
                # Wrap stream of PCM chunks into a continuous WAV stream header + data
                # First yield a minimal WAV header with 24kHz mono PCM16
                import struct
                yield b'RIFF' + (b'\x00\x00\x00\x00') + b'WAVEfmt ' + struct.pack('<IHHIIHH',16,1,1,24000,24000*2,2,16) + b'data' + (b'\x00\x00\x00\x00')
                for chunk in gen:
                    yield chunk
            return Response(stream_with_context(generate()), mimetype='audio/wav')
        except Exception as e:
            print('chat_stream error', e)
            print(traceback.format_exc())
            return jsonify({'error':'internal','message':str(e)}), 500


def create_app():
    return OmniChatServer(run_app=False).app

def serve(ip='0.0.0.0', port=60808, device='cuda:0'):
    OmniChatServer(ip, port, True, './checkpoint', device)

if __name__=='__main__':
    import fire
    fire.Fire(serve)

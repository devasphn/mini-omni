import sys, os, base64, tempfile, traceback, struct, time, uuid
from flask import Flask, Response, stream_with_context, render_template_string, jsonify, request
from inference import OmniInference

REALTIME_HTML = r'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Mini-Omni Realtime</title><style>body{font-family:system-ui,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px} .card{max-width:1100px;margin:0 auto;background:#111827;border:1px solid #1f2937;border-radius:16px;padding:24px} h1{margin:0 0 12px} .grid{display:grid;grid-template-columns:1fr 320px;gap:16px} .btn{padding:10px 16px;border:none;border-radius:9999px;color:#fff;background:#2563eb;cursor:pointer} .status{padding:8px 10px;border-radius:10px;margin:10px 0;background:#064e3b;border:1px solid #10b981} audio{width:100%;margin-top:10px} .panel{background:#0b1220;border-radius:10px;padding:12px} .row{display:flex;gap:8px;align-items:center} .bar{height:8px;background:#1f2937;border-radius:8px;overflow:hidden} .bar>span{display:block;height:100%;background:#22c55e;width:0%} label{font-size:12px;color:#93a3af}</style></head><body><div class="card"><h1>🎙️ Mini-Omni Realtime</h1><div class="grid"><div><div id="status" class="status">Mic off</div><div class="row"><button id="toggle" class="btn">Enable Mic</button><button id="force" class="btn" style="background:#7c3aed">Force Send</button></div><div class="panel" style="margin-top:10px"><div class="row" style="justify-content:space-between"><label>VAD sensitivity</label><input id="sens" type="range" min="2000" max="20000" step="500" value="5000"/><span id="sensVal">5000</span></div><div class="row" style="justify-content:space-between"><label>Silence hangover (frames)</label><input id="hang" type="range" min="3" max="25" step="1" value="10"/><span id="hangVal">10</span></div><div class="row" style="gap:12px"><label>Energy</label><div class="bar" style="flex:1"><span id="energy"></span></div><span id="state">silence</span></div></div><audio id="player" controls></audio></div><div class="panel"><div style="font-weight:700;margin-bottom:6px">Logs</div><pre id="log" style="white-space:pre-wrap;max-height:420px;overflow:auto"></pre></div></div></div><script type="module">const statusEl=document.getElementById('status');const btn=document.getElementById('toggle');const player=document.getElementById('player');const log=document.getElementById('log');const forceBtn=document.getElementById('force');const energyBar=document.getElementById('energy');const stateEl=document.getElementById('state');const sens=document.getElementById('sens');const sensVal=document.getElementById('sensVal');const hang=document.getElementById('hang');const hangVal=document.getElementById('hangVal');let mediaStream, audioCtx, source, workletNode;function ts(){return new Date().toISOString().split('T')[1].replace('Z','');}function logln(t){log.textContent += `[${ts()}] ${t}\n`;log.scrollTop=log.scrollHeight;}sens.addEventListener('input',()=>{sensVal.textContent=sens.value; if(workletNode) workletNode.port.postMessage({cmd:'cfg', sens:+sens.value});});hang.addEventListener('input',()=>{hangVal.textContent=hang.value; if(workletNode) workletNode.port.postMessage({cmd:'cfg', hang:+hang.value});});async function start(){try{ audioCtx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:16000}); await audioCtx.audioWorklet.addModule('/worklet.js'); mediaStream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,sampleRate:16000}}); source=audioCtx.createMediaStreamSource(mediaStream); workletNode=new AudioWorkletNode(audioCtx,'pcm-capture'); source.connect(workletNode); workletNode.connect(audioCtx.destination); workletNode.port.postMessage({cmd:'cfg', sens:+sens.value, hang:+hang.value}); workletNode.port.onmessage = async (ev)=>{ const m=ev.data; if(!m) return; if(m.type==='meter'){ const pct=Math.min(100, Math.round(m.energy/30000*100)); energyBar.style.width=pct+'%'; stateEl.textContent=m.state; } else if(m.type==='emit'){ const reqId=crypto.randomUUID(); const samples = m.size; logln(`VAD emit → uploading segment id=${reqId} frames=${samples}`); workletNode.port.postMessage({cmd:'pop', id:reqId}); } else if(m.type==='frames'){ const reqId=m.id||'noid'; const frames=m.data; const bytes=frames.length*2; logln(`upload id=${reqId} bytes=${bytes}`); const b64 = base64FromInt16(new Int16Array(frames)); const t0=performance.now(); const res = await fetch('/stream/vad',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pcm16:b64, id:reqId})}); if(!res.ok){ logln(`server ${reqId} HTTP ${res.status}`); return;} const blob = await res.blob(); logln(`server ${reqId} responded in ${Math.round(performance.now()-t0)} ms, size=${blob.size}`); player.src=URL.createObjectURL(blob); await player.play().catch(()=>{}); logln(`play ${reqId} start`); } }; statusEl.textContent='Mic on (realtime VAD)'; btn.textContent='Disable Mic'; logln('mic enabled'); }catch(e){ logln('start error: '+e.message);} } async function stop(){ try{ if(workletNode){workletNode.disconnect(); workletNode=null;} if(source){source.disconnect(); source=null;} if(mediaStream){mediaStream.getTracks().forEach(t=>t.stop()); mediaStream=null;} if(audioCtx){await audioCtx.close(); audioCtx=null;} statusEl.textContent='Mic off'; btn.textContent='Enable Mic'; logln('mic disabled'); }catch(e){ logln('stop error: '+e.message);} } function base64FromInt16(int16){ const bytes = new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength); let binary=''; const step=0x8000; for(let i=0;i<bytes.length;i+=step){ binary+=String.fromCharCode.apply(null, bytes.subarray(i,i+step)); } return btoa(binary);} btn.addEventListener('click', async()=>{ if(!audioCtx){ await start(); } else { await stop(); } }); forceBtn.addEventListener('click',()=>{ if(workletNode) workletNode.port.postMessage({cmd:'force'}); });</script></body></html>'''

WORKLET_JS = r'''class RingQ{constructor(cap){this.buf=new Int16Array(cap);this.head=0;this.tail=0;this.size=0;}push(arr){for(let i=0;i<arr.length;i++){this.buf[this.head]=arr[i];this.head=(this.head+1)%this.buf.length;if(this.size<this.buf.length){this.size++;}else{this.tail=(this.tail+1)%this.buf.length;}}}popAll(){const out=new Int16Array(this.size);for(let i=0;i<this.size;i++){out[i]=this.buf[(this.tail+i)%this.buf.length];}this.head=0;this.tail=0;const s=this.size;this.size=0;return out;}}class PcmProcessor extends AudioWorkletProcessor{constructor(){super();this.ring=new RingQ(16000*10);this.state='silence';this.hang=10;this.sens=5000;this.tmp=null;this.port.onmessage=(ev)=>{const m=ev.data;if(!m)return;if(m.cmd==='cfg'){if(m.sens) this.sens=m.sens;if(m.hang) this.hang=m.hang;}else if(m.cmd==='pop'){const frames=this.ring.popAll();this.port.postMessage({type:'frames',data:frames,id:m.id});}else if(m.cmd==='force'){const frames=this.ring.popAll();this.port.postMessage({type:'frames',data:frames,id:crypto.randomUUID?crypto.randomUUID():(Math.random()+'')});}};}process(inputs){const input=inputs[0];if(!input||!input[0]) return true;const f32=input[0];if(!this.tmp||this.tmp.length!==f32.length){this.tmp=new Int16Array(f32.length);}let energy=0;for(let i=0;i<f32.length;i++){const s=Math.max(-1,Math.min(1,f32[i]));const q=(s<0?s*0x8000:s*0x7FFF)|0;this.tmp[i]=q;energy+=q*q;}energy/=this.tmp.length;const talking=energy>this.sens;if(talking){this.state='speech';this.sil=0;}else{this.sil=(this.sil||0)+1;if(this.state==='speech'&&this.sil>=this.hang){this.port.postMessage({type:'emit',size:this.ring.size});this.state='silence';this.sil=0;}}this.ring.push(this.tmp);this.port.postMessage({type:'meter',energy, state:this.state});return true;}}registerProcessor('pcm-capture',PcmProcessor);'''

class OmniChatServer:
    def __init__(self, ip='0.0.0.0', port=60808, run_app=True, ckpt_dir='./checkpoint', device='cuda:0'):
        app = Flask(__name__)
        self.client = OmniInference(ckpt_dir, device)
        self.client.warm_up()
        self.app = app
        app.add_url_rule('/', view_func=self.realtime)
        app.add_url_rule('/worklet.js', view_func=self.worklet)
        app.add_url_rule('/stream/vad', methods=['POST'], view_func=self.stream_vad)
        app.add_url_rule('/health', view_func=self.health)
        if run_app:
            app.run(host=ip, port=port, threaded=False)

    def realtime(self):
        return render_template_string(REALTIME_HTML)

    def worklet(self):
        return Response(WORKLET_JS, mimetype='application/javascript')

    def health(self):
        return jsonify({'status':'ok'})

    def stream_vad(self):
        try:
            t0=time.time();
            payload = request.get_json(force=True)
            req_id = payload.get('id') or str(uuid.uuid4())
            raw_b64 = payload.get('pcm16')
            if not raw_b64:
                return jsonify({'error':'missing pcm16'}), 400
            raw = base64.b64decode(raw_b64.encode('utf-8'))
            print(f"[recv] id={req_id} bytes={len(raw)}")
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(self._pcm16_to_wav(raw, 16000))
                path = f.name
            gen = self.client.run_AT_batch_stream(path, stream_stride=4)
            def wav_bytes():
                header = b'RIFF' + struct.pack('<I', 36) + b'WAVEfmt ' + struct.pack('<IHHIIHH',16,1,1,24000,24000*2,2,16) + b'data' + struct.pack('<I', 0)
                yield header
                first=True
                for chunk in gen:
                    if first:
                        print(f"[first] id={req_id} dt={int((time.time()-t0)*1000)}ms")
                        first=False
                    try:
                        yield chunk if isinstance(chunk, (bytes,bytearray)) else bytes(chunk)
                    except Exception:
                        pass
            return Response(stream_with_context(wav_bytes()), mimetype='audio/wav')
        except Exception as e:
            print('stream_vad error', e)
            print(traceback.format_exc())
            return jsonify({'error':'internal','message':str(e)}), 500

    @staticmethod
    def _pcm16_to_wav(pcm_bytes: bytes, sr: int) -> bytes:
        data_size = len(pcm_bytes)
        header = b'RIFF' + struct.pack('<I', 36+data_size) + b'WAVEfmt ' + struct.pack('<IHHIIHH',16,1,1,sr,sr*2,2,16) + b'data' + struct.pack('<I', data_size)
        return header + pcm_bytes


def create_app():
    return OmniChatServer(run_app=False).app

def serve(ip='0.0.0.0', port=60808, device='cuda:0'):
    OmniChatServer(ip, port, True, './checkpoint', device)

if __name__=='__main__':
    import fire
    fire.Fire(serve)

import sys, os, base64, tempfile, traceback, struct
from flask import Flask, Response, stream_with_context, render_template_string, jsonify, request
from inference import OmniInference

REALTIME_HTML = r'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Mini-Omni Realtime</title><style>body{font-family:system-ui,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px} .card{max-width:1000px;margin:0 auto;background:#111827;border:1px solid #1f2937;border-radius:16px;padding:24px} h1{margin:0 0 12px} .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center} .btn{padding:10px 16px;border:none;border-radius:9999px;color:#fff;background:#2563eb;cursor:pointer} .status{padding:8px 10px;border-radius:10px;margin:10px 0;background:#064e3b;border:1px solid #10b981} audio{width:100%;margin-top:10px}</style></head><body><div class="card"><h1>🎙️ Mini-Omni Realtime</h1><div id="status" class="status">Mic off</div><div class="row"><button id="toggle" class="btn">Enable Mic</button></div><audio id="player" controls></audio><pre id="log" style="white-space:pre-wrap;background:#0b1220;border-radius:10px;padding:12px;max-height:240px;overflow:auto"></pre></div><script type="module">const statusEl=document.getElementById('status');const btn=document.getElementById('toggle');const player=document.getElementById('player');const log=document.getElementById('log');let mediaStream, audioCtx, source, workletNode;function logln(t){log.textContent += t+'\n';log.scrollTop=log.scrollHeight;}async function start(){try{ audioCtx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:16000}); await audioCtx.audioWorklet.addModule('/worklet.js'); mediaStream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,sampleRate:16000}}); source=audioCtx.createMediaStreamSource(mediaStream); workletNode=new AudioWorkletNode(audioCtx,'pcm-capture'); source.connect(workletNode); workletNode.connect(audioCtx.destination); workletNode.port.onmessage = async (ev)=>{ const msg=ev.data; if(!msg) return; if(msg.type==='emit'){ // VAD emitted a segment
 workletNode.port.postMessage({cmd:'pop'}); } else if(msg.type==='frames'){ const pcm = new Int16Array(msg.data); const b64 = base64FromInt16(pcm); fetchAndPlay('/stream/vad',{pcm16:b64}); } }; statusEl.textContent='Mic on (realtime VAD)'; btn.textContent='Disable Mic'; }catch(e){ logln('start error: '+e.message);} } async function stop(){ try{ if(workletNode){workletNode.disconnect(); workletNode=null;} if(source){source.disconnect(); source=null;} if(mediaStream){mediaStream.getTracks().forEach(t=>t.stop()); mediaStream=null;} if(audioCtx){await audioCtx.close(); audioCtx=null;} statusEl.textContent='Mic off'; btn.textContent='Enable Mic'; }catch(e){ logln('stop error: '+e.message);} } function base64FromInt16(int16){ const bytes = new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength); let binary=''; const step=0x8000; for(let i=0;i<bytes.length;i+=step){ binary+=String.fromCharCode.apply(null, bytes.subarray(i,i+step)); } return btoa(binary);} async function fetchAndPlay(url, body){ try{ const res = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); if(!res.ok) throw new Error('HTTP '+res.status); const blob = await res.blob(); player.src = URL.createObjectURL(blob); await player.play().catch(()=>{}); } catch(e){ logln('play error: '+e.message);} } btn.addEventListener('click', async()=>{ if(!audioCtx){ await start(); } else { await stop(); } });</script></body></html>'''

WORKLET_JS = r'''class RingQ { constructor(capacity){ this.buf=new Int16Array(capacity); this.head=0; this.tail=0; this.size=0; } push(arr){ const n=arr.length; for(let i=0;i<n;i++){ this.buf[this.head]=arr[i]; this.head=(this.head+1)%this.buf.length; if(this.size<this.buf.length){ this.size++; } else { this.tail=(this.tail+1)%this.buf.length; } } } popAll(){ const out=new Int16Array(this.size); for(let i=0;i<this.size;i++){ out[i]=this.buf[(this.tail+i)%this.buf.length]; } this.head=0; this.tail=0; const sz=this.size; this.size=0; return out; } } class PcmProcessor extends AudioWorkletProcessor { constructor(){ super(); this.ring=new RingQ(16000*5); this.vadState='silence'; this.silenceFrames=0; this.tmp=null; this.frameSamples=320; // 20ms @16k
 this.port.onmessage = (ev)=>{ const msg=ev.data; if(!msg) return; if(msg.cmd==='pop'){ const frames=this.ring.popAll(); this.port.postMessage({type:'frames', data:frames}); } }; } process(inputs){ const input=inputs[0]; if(!input||!input[0]) return true; const f32=input[0]; if(!this.tmp||this.tmp.length!==f32.length){ this.tmp=new Int16Array(f32.length);} let energy=0; for(let i=0;i<f32.length;i++){ const s=Math.max(-1,Math.min(1,f32[i])); const q=(s<0?s*0x8000:s*0x7FFF)|0; this.tmp[i]=q; energy += q*q; } energy/=this.tmp.length; const th=5000; if(energy>th){ this.vadState='speech'; this.silenceFrames=0; } else { this.silenceFrames++; if(this.vadState==='speech' && this.silenceFrames>=10){ this.port.postMessage({type:'emit'}); this.vadState='silence'; } } this.ring.push(this.tmp); return true; } } registerProcessor('pcm-capture', PcmProcessor);'''

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
            data = request.get_json(force=True)
            if not data or 'pcm16' not in data:
                return jsonify({'error':'missing pcm16'}), 400
            raw = base64.b64decode(data['pcm16'].encode('utf-8'))
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(self._pcm16_to_wav(raw, 16000))
                path = f.name
            gen = self.client.run_AT_batch_stream(path, stream_stride=4)
            def wav_bytes():
                header = b'RIFF' + struct.pack('<I', 36) + b'WAVEfmt ' + struct.pack('<IHHIIHH',16,1,1,24000,24000*2,2,16) + b'data' + struct.pack('<I', 0)
                yield header
                for chunk in gen:
                    if isinstance(chunk, bytes):
                        yield chunk
                    else:
                        try: yield bytes(chunk)
                        except: pass
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

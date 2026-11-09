#!/usr/bin/env python3
"""PNG Quant Preview: native macOS window around the real pngquant binary.

Dev run:   python3 pngquant_preview_app.py [--pngquant PATH]
Packaged:  see setup.py (py2app) or the PyInstaller command in the notes.
"""
import argparse, base64, os, re, shutil, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import webview

SIPS = "/usr/bin/sips"  # built into macOS: converts to PNG and resizes by width


def find_pngquant(cli_path=None):
    candidates = []
    if cli_path:
        candidates.append(os.path.expanduser(cli_path))
    # Check local directories first (for development)
    candidates.append(os.path.join(os.getcwd(), "pngquant"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pngquant"))
    # Check common system locations
    candidates += ["/opt/homebrew/bin/pngquant", "/usr/local/bin/pngquant"]
    # Check bundled app resources
    for base in (os.environ.get("RESOURCEPATH"), getattr(sys, "_MEIPASS", None)):
        if base:
            candidates.append(os.path.join(base, "pngquant"))
    # Check user scripts
    candidates.append(os.path.expanduser("~/scripts/pngquant"))
    # Check PATH
    found = shutil.which("pngquant")
    if found:
        candidates.append(found)
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            try:
                if subprocess.run([c, "--version"], capture_output=True, timeout=5).returncode == 0:
                    return c
            except Exception:
                pass
    return None


ap = argparse.ArgumentParser()
ap.add_argument("--pngquant")
args, _ = ap.parse_known_args()
PNGQUANT = find_pngquant(args.pngquant)

PAGE = """<!doctype html><meta charset=utf-8><title>PNG Quant Preview</title>
<style>
:root{color-scheme:light dark;--bg:#fff;--fg:#111;--mut:#777;--bd:#ccc;--ck:#e6e6e6}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#999;--bd:#444;--ck:#2a2a2a}}
body{margin:0;font:14px -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;gap:18px;align-items:center;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid var(--bd);position:sticky;top:0;background:var(--bg);z-index:1}
input[type=number]{width:70px;font:inherit;padding:4px 6px;border:1px solid var(--bd);border-radius:6px;background:none;color:var(--fg)}
button{font:inherit;padding:6px 12px;border:1px solid var(--bd);background:none;color:var(--fg);border-radius:6px;cursor:pointer}
#drop{margin:16px;border:2px dashed var(--bd);border-radius:10px;padding:60px;text-align:center;color:var(--mut)}
#drop.over{border-color:var(--fg);color:var(--fg)}
#grid{display:none;padding:16px;gap:16px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
#grid.on{display:grid}
.card{border:1px solid var(--bd);border-radius:8px;padding:8px;cursor:pointer}
.card:hover{outline:2px solid var(--fg)}
.card .im{min-height:120px;display:flex;align-items:center;justify-content:center;border-radius:4px;
  background:repeating-conic-gradient(var(--ck) 0 25%,transparent 0 50%) 0 0/16px 16px}
.card img{max-width:100%;display:block}
.px .card img{image-rendering:pixelated}
.cap{margin-top:6px;display:flex;justify-content:space-between;gap:8px}
.mut{color:var(--mut)}
</style>
<header>
 <label>Colors from <input id=s type=number min=2 max=247 value=2> <span class=mut>(10 previews)</span></label>
 <label>Width <input id=w type=number min=1 max=10000 placeholder=orig> px</label>
 <label><input id=nd type=checkbox> no dither</label>
 <label><input id=px type=checkbox> pixelated</label>
 <span id=stat class=mut></span>
 <button onclick="f.click()">Open image</button>
</header>
<div id=drop>Drop an image here, or click to choose<input id=f type=file accept="image/*" hidden></div>
<div id=grid></div>
<script>
const $=i=>document.getElementById(i);
let file=null,timer=0,seq=0;
const fmt=b=>b>1048576?(b/1048576).toFixed(2)+' MB':(b/1024).toFixed(1)+' KB';
$('drop').onclick=()=>$('f').click();
$('f').onchange=e=>{load(e.target.files[0]);e.target.value=''};
document.body.ondragover=e=>{e.preventDefault();$('drop').classList.add('over')};
document.body.ondragleave=()=>$('drop').classList.remove('over');
document.body.ondrop=e=>{e.preventDefault();$('drop').classList.remove('over');load(e.dataTransfer.files[0])};
function load(x){
  if(!x)return; file=x;
  $('drop').style.display='none'; $('grid').classList.add('on'); run();
}
['s','w','nd'].forEach(i=>$(i).oninput=()=>{clearTimeout(timer);timer=setTimeout(run,300)});
$('px').onchange=()=>document.body.classList.toggle('px',$('px').checked);

async function save(name,blob){
  if(window.pywebview&&pywebview.api){
    const b64=await new Promise(r=>{const fr=new FileReader();fr.onload=()=>r(fr.result.split(',')[1]);fr.readAsDataURL(blob)});
    const saved=await pywebview.api.save(name,b64);
    if(saved)$('stat').textContent='Saved '+saved;
  }else{
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();
  }
}

async function run(){
  if(!file)return; const my=++seq; $('stat').textContent='preparing…';
  const w=Math.max(0,parseInt($('w').value)||0);
  const start=Math.max(2,Math.min(247,parseInt($('s').value)||2));
  const ext=(file.name.split('.').pop()||'png').toLowerCase();
  const base=file.name.replace(/\\.[^.]+$/,'');
  const pr=await fetch('/prepare?'+new URLSearchParams({width:w,ext}),{method:'POST',body:file});
  if(my!==seq)return;
  if(!pr.ok){$('stat').textContent='Error: '+await pr.text();return}
  const src=await pr.blob();
  const bmp=await createImageBitmap(src);
  $('stat').textContent='Source '+bmp.width+'×'+bmp.height+' · '+fmt(src.size)+' (PNG, before quantizing)';
  bmp.close();

  const grid=$('grid'); grid.innerHTML='';
  const nd=$('nd').checked?1:0;
  await Promise.all(Array.from({length:10},(_,i)=>start+i).map(async n=>{
    const card=document.createElement('div'); card.className='card';
    card.innerHTML='<div class=im></div><div class=cap><b>'+n+' colors</b><span class=mut>…</span></div>';
    grid.appendChild(card);
    const im=card.querySelector('.im'),info=card.querySelector('.cap span');
    const res=await fetch('/quantize?'+new URLSearchParams({colors:n,nofs:nd}),{method:'POST',body:src});
    if(my!==seq)return;
    if(!res.ok){info.textContent='error';im.textContent=await res.text();return}
    const blob=await res.blob();
    const img=new Image(); img.src=URL.createObjectURL(blob); im.appendChild(img);
    info.textContent=fmt(blob.size)+' · click to save';
    card.onclick=()=>save(base+'-'+n+(w?'-w'+w:'')+'.png',blob);
  }));
}
</script>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, PAGE.encode(), "text/html; charset=utf-8")

    def do_POST(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        data = self.rfile.read(int(self.headers["Content-Length"]))

        if url.path == "/prepare":
            # Convert any input to PNG (pngquant only reads PNG) and optionally
            # resize by width, keeping the aspect ratio (no cropping).
            width = int(q.get("width", ["0"])[0])
            ext = re.sub(r"[^a-z0-9]", "", q.get("ext", ["png"])[0].lower()) or "png"
            with tempfile.TemporaryDirectory() as d:
                src, dst = os.path.join(d, "in." + ext), os.path.join(d, "out.png")
                with open(src, "wb") as fh:
                    fh.write(data)
                cmd = [SIPS, "-s", "format", "png"]
                if width > 0:
                    cmd += ["--resampleWidth", str(width)]
                cmd += [src, "--out", dst]
                p = subprocess.run(cmd, capture_output=True)
                if p.returncode != 0 or not os.path.exists(dst):
                    msg = p.stderr.decode(errors="replace") or p.stdout.decode(errors="replace") or "sips failed"
                    return self._send(500, msg.encode())
                with open(dst, "rb") as fh:
                    return self._send(200, fh.read(), "image/png")

        if url.path == "/quantize":
            colors = max(2, min(256, int(q.get("colors", ["32"])[0])))
            cmd = [PNGQUANT, "-v", str(colors)]
            if q.get("nofs", ["0"])[0] == "1":
                cmd.append("--nofs")
            cmd.append("-")  # stdin -> stdout
            p = subprocess.run(cmd, input=data, capture_output=True)
            if p.returncode != 0:
                msg = p.stderr.decode(errors="replace") or f"pngquant exit {p.returncode}"
                return self._send(500, msg.encode())
            return self._send(200, p.stdout, "image/png")

        self._send(404, b"not found")


class Api:
    """Exposed to the page as window.pywebview.api"""
    window = None

    def save(self, name, b64):
        save_type = webview.FileDialog.SAVE if hasattr(webview, "FileDialog") else webview.SAVE_DIALOG
        result = self.window.create_file_dialog(save_type, save_filename=name)
        if not result:
            return None
        path = result if isinstance(result, str) else result[0]
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(b64))
        return os.path.basename(path)


def main():
    if not PNGQUANT:
        webview.create_window("PNG Quant Preview", html="<body style='font:16px system-ui;padding:40px'>pngquant binary not found.<br>Bundle it, or run with <code>--pngquant PATH</code>.</body>")
        webview.start()
        return
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # free port, no clashes
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = Api()
    api.window = webview.create_window(
        "PNG Quant Preview", f"http://127.0.0.1:{server.server_address[1]}",
        js_api=api, width=1280, height=820, min_size=(720, 480))
    webview.start()  # returns when the window is closed, app exits


if __name__ == "__main__":
    main()

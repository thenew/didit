#!/usr/bin/env python3
"""Didit: native macOS window around the real pngquant binary.

Dev run:   python3 pngquant_preview_app.py [--pngquant PATH]
Packaged:  see setup.py (py2app) or the PyInstaller command in the notes.
"""
import argparse, base64, os, re, shutil, subprocess, sys, tempfile, threading, json
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



PAGE = """<!doctype html><meta charset=utf-8><title>Didit</title>
<style>
:root{color-scheme:light dark;--bg:#fff;--fg:#111;--mut:#777;--bd:#ccc;--ck:#e6e6e6;--accent:#007aff;--zoom-bg:#f0f0f0}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#999;--bd:#444;--ck:#2a2a2a;--accent:#007aff;--zoom-bg:#2a2a2a}}
body{margin:0;font:14px -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;gap:18px;align-items:center;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid var(--bd);position:sticky;top:0;background:var(--bg);z-index:1}
input[type=number]{width:70px;font:inherit;padding:4px 6px;border:1px solid var(--bd);border-radius:6px;background:none;color:var(--fg)}
button, .button-like{font:inherit;padding:6px 12px;border:1px solid var(--bd);background:none;color:var(--fg);border-radius:6px;cursor:pointer}
button:hover, .button-like:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
#drop{margin:16px;border:2px dashed var(--bd);border-radius:10px;padding:60px;text-align:center;color:var(--mut)}
#drop.over{border-color:var(--accent);color:var(--fg)}
#grid{display:none;padding:16px;gap:16px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
#grid.on{display:grid}
#file-list{display:none;padding:16px;gap:24px}
#file-list.on{display:block}
.file-section{border:1px solid var(--bd);border-radius:8px;padding:16px}
.file-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.file-name{font-weight:600;color:var(--fg)}
.file-controls{display:flex;gap:8px;align-items:center}
.file-grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
.card{border:1px solid var(--bd);border-radius:8px;padding:8px;cursor:pointer;position:relative}
.card:hover{outline:2px solid var(--accent)}
.card.selected{outline:2px solid var(--accent);background:rgba(0,122,255,0.1)}
.card .im{min-height:120px;display:flex;align-items:center;justify-content:center;border-radius:4px;
  background:repeating-conic-gradient(var(--ck) 0 25%,transparent 0 50%) 0 0/16px 16px}
.card.zoom .im{min-height:auto}
.card.zoom img{max-width:100%;max-height:80vh;display:block}
.card img{max-width:100%;display:block}
.px .card img{image-rendering:pixelated}
.cap{margin-top:6px;display:flex;justify-content:space-between;gap:8px;align-items:center}
.mut{color:var(--mut)}
.checkbox-wrapper{display:flex;align-items:center;gap:6px;cursor:pointer}
.checkbox-wrapper input[type=checkbox]{width:16px;height:16px;accent-color:var(--accent)}
.download-toolbar{display:flex;gap:12px;align-items:center;margin-top:16px;padding:12px;border-top:1px solid var(--bd)}
#zoom-toggle{display:flex;align-items:center;gap:6px}
.stats-bar{display:flex;gap:16px;align-items:center;margin-left:auto}
</style>
<header>
 <label>Colors from <input id=s type=number min=2 max=247 value=2> <span class=mut>(4 previews per file)</span></label>
 <label>Width <input id=w type=number min=1 max=10000 value=1200> px</label>
 <label><input id=nd type=checkbox> no dither</label>
 <label><input id=px type=checkbox> pixelated</label>
 <button id="zoom-toggle" onclick="toggleZoom()">
   <span id="zoom-icon">🔍</span> <span id="zoom-text">100% Size</span>
 </button>
 <span id=stat class=mut></span>
 <button onclick="f.click()">Open image(s)</button>
</header>
<div id=drop>Drop image(s) here, or click to choose<input id=f type=file accept="image/*" multiple hidden></div>
<div id=file-list></div>
<script>
const $=i=>document.getElementById(i);
let files=[],timer=0,zoomMode=false;
const fmt=b=>b>1048576?(b/1048576).toFixed(2)+' MB':(b/1024).toFixed(1)+' KB';

// Toggle zoom mode
function toggleZoom(){
  zoomMode=!zoomMode;
  if(zoomMode){
    $('zoom-text').textContent='Fit to Grid';
    $('zoom-icon').textContent='🔍';
    document.body.classList.add('zoomed');
  }else{
    $('zoom-text').textContent='100% Size';
    document.body.classList.remove('zoomed');
  }
  // Re-apply zoom to all existing cards
  document.querySelectorAll('.card').forEach(c=>{
    if(zoomMode) c.classList.add('zoom');
    else c.classList.remove('zoom');
  });
}

// Get selected cards across all files
function getSelectedCards(){
  const selected=[];
  document.querySelectorAll('.card.selected').forEach(card=>{
    const fileIdx=parseInt(card.dataset.fileIdx);
    const color=parseInt(card.dataset.colors);
    const blob=card._blob;
    const baseName=files[fileIdx].name.replace(/\\.[^.]+$/,'');
    const width=$('w').value||0;
    selected.push({fileIdx,color,blob,baseName,width});
  });
  return selected;
}

// Download all selected files
async function downloadSelected(){
  const selected=getSelectedCards();
  if(selected.length===0){
    $('stat').textContent='No files selected';
    return;
  }
  
  if(window.pywebview&&pywebview.api){
    const promises=selected.map(async ({fileIdx,color,blob,baseName,width})=>{
      const b64=await new Promise(r=>{const fr=new FileReader();fr.onload=()=>r(fr.result.split(',')[1]);fr.readAsDataURL(blob)});
      const name=baseName+'-'+color+(width?'-w'+width:'')+'.png';
      return pywebview.api.save(name,b64);
    });
    const results=await Promise.all(promises);
    const saved=results.filter(r=>r).length;
    $('stat').textContent=`Saved ${saved} of ${selected.length} files`;
  }else{
    selected.forEach(({fileIdx,color,blob,baseName,width})=>{
      const name=baseName+'-'+color+(width?'-w'+width:'')+'.png';
      const a=document.createElement('a');
      a.href=URL.createObjectURL(blob);
      a.download=name;
      a.click();
    });
    $('stat').textContent=`Downloaded ${selected.length} files`;
  }
}

// Select/Deselect all cards
function toggleSelectAll(){
  const allCards=document.querySelectorAll('.card');
  const anySelected=[...allCards].some(c=>c.classList.contains('selected'));
  allCards.forEach(card=>{
    if(anySelected) card.classList.remove('selected');
    else card.classList.add('selected');
  });
  updateToolbar();
}

// Update download toolbar visibility
function updateToolbar(){
  const selected=document.querySelectorAll('.card.selected').length;
  const toolbar=$('download-toolbar');
  if(!toolbar) return;
  if(selected>0){
    toolbar.style.display='flex';
    toolbar.querySelector('span').textContent=`${selected} file(s) selected`;
  }else{
    toolbar.style.display='none';
  }
}

// Handle card selection
function setupCardSelection(card, blob, fileIdx, color, baseName, width){
  card._blob=blob;
  card.dataset.fileIdx=fileIdx;
  card.dataset.colors=color;
  card.dataset.baseName=baseName;
  card.dataset.width=width;
  
  card.addEventListener('click', (e)=>{
    if(e.ctrlKey||e.metaKey){
      // Ctrl/Cmd+click: toggle selection
      e.preventDefault();
      card.classList.toggle('selected');
      updateToolbar();
    }else if(e.target.tagName!=='INPUT'&&e.target.tagName!=='IMG'){
      // Regular click: save single file
      const name=baseName+'-'+color+(width?'-w'+width:'')+'.png';
      save(name, blob);
    }
  });
  
  // Add checkbox for selection
  const checkboxWrapper=document.createElement('div');
  checkboxWrapper.className='checkbox-wrapper';
  checkboxWrapper.innerHTML=`<input type="checkbox" ${card.classList.contains('selected')?'checked':''}>`;
  checkboxWrapper.addEventListener('click', (e)=>{e.stopPropagation();});
  checkboxWrapper.querySelector('input').addEventListener('change', (e)=>{e.stopPropagation();card.classList.toggle('selected');updateToolbar();});
  card.querySelector('.cap').prepend(checkboxWrapper);
}

$('drop').onclick=()=>$('f').click();
$('f').oninput=e=>{if(e.target.files.length>0)load(Array.from(e.target.files));e.target.value=''};
document.body.ondragover=e=>{e.preventDefault();$('drop').classList.add('over')};
document.body.ondragleave=()=>$('drop').classList.remove('over');
document.body.ondrop=e=>{e.preventDefault();$('drop').classList.remove('over');load(Array.from(e.dataTransfer.files))};

function load(newFiles){
  if(!newFiles||newFiles.length===0)return;
  files=[...newFiles];
  $('drop').style.display='none';
  $('file-list').classList.add('on');
  renderFileList();
}

function renderFileList(){
  const fileList=$('file-list');
  fileList.innerHTML='';
  
  // Add download toolbar
  const toolbar=document.createElement('div');
  toolbar.id='download-toolbar';
  toolbar.className='download-toolbar';
  toolbar.style.display='none';
  toolbar.innerHTML=`
    <button onclick="toggleSelectAll()">Toggle All</button>
    <span class="mut"></span>
    <button onclick="downloadSelected()" style="background:var(--accent);color:#fff;border-color:var(--accent)">Download Selected</button>
  `;
  fileList.appendChild(toolbar);
  
  files.forEach((file, fileIdx)=>{
    const section=document.createElement('div');
    section.className='file-section';
    section.id=`file-${fileIdx}`;
    
    const header=document.createElement('div');
    header.className='file-header';
    header.innerHTML=`
      <span class="file-name">${file.name}</span>
      <div class="file-controls">
        <span class="mut">${fmt(file.size)}</span>
      </div>
    `;
    
    const grid=document.createElement('div');
    grid.className='file-grid';
    grid.id=`file-grid-${fileIdx}`;
    
    section.appendChild(header);
    section.appendChild(grid);
    fileList.appendChild(section);
  });
  
  // Process all files
  files.forEach((file, fileIdx)=>{processFile(file, fileIdx);});
}

async function processFile(file, fileIdx){
  if(!file)return;
  const grid=document.getElementById(`file-grid-${fileIdx}`);
  grid.innerHTML='<div class="mut" style="padding:20px">Processing...</div>';
  
  const w=Math.max(0,parseInt($('w').value)||0);
  const start=Math.max(2,Math.min(247,parseInt($('s').value)||2));
  const ext=(file.name.split('.').pop()||'png').toLowerCase();
  const base=file.name.replace(/\\.[^.]+$/,'');
  const nd=$('nd').checked?1:0;
  
  const pr=await fetch('/prepare?'+new URLSearchParams({width:w,ext,fileIdx}),{method:'POST',body:file});
  if(!pr.ok){grid.innerHTML=`<div class="mut" style="padding:20px">Error: ${await pr.text()}</div>`;return}
  const src=await pr.blob();
  
  const bmp=await createImageBitmap(src);
  const statEl=document.createElement('div');
  statEl.className='mut';
  statEl.style.margin='4px 0';
  statEl.textContent=`Source ${bmp.width}×${bmp.height} · ${fmt(src.size)} (PNG, before quantizing)`;
  grid.prepend(statEl);
  bmp.close();

  // Generate 4 previews instead of 10 (faster)
  await Promise.all(Array.from({length:4},(_,i)=>start+i).map(async n=>{
    const card=document.createElement('div'); card.className='card';
    if(zoomMode) card.classList.add('zoom');
    card.innerHTML='<div class=im></div><div class=cap><b>'+n+' colors</b><span class=mut>…</span></div>';
    grid.appendChild(card);
    const im=card.querySelector('.im'),info=card.querySelector('.cap span');
    
    const res=await fetch('/quantize?'+new URLSearchParams({colors:n,nofs:nd,fileIdx}),{method:'POST',body:src});
    if(!res.ok){info.textContent='error';im.textContent=await res.text();return}
    const blob=await res.blob();
    const img=new Image();
    img.src=URL.createObjectURL(blob);
    im.appendChild(img);
    info.textContent=fmt(blob.size)+' · click to save';
    
    setupCardSelection(card, blob, fileIdx, n, base, w>0?w:0);
  }));
}

['s','w','nd'].forEach(i=>$(i).oninput=()=>{if(files.length>0){clearTimeout(timer);timer=setTimeout(()=>{files.forEach((f,idx)=>processFile(f,idx));},500)}});
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
        
        # Get file index if provided
        file_idx = int(q.get("fileIdx", [0])[0]) if q.get("fileIdx") else 0
        
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
                    processed_data = fh.read()
                
                return self._send(200, processed_data, "image/png")

        if url.path == "/quantize":
            # Use the data sent from frontend (already processed PNG)
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
        webview.create_window("Didit", html="<body style='font:16px system-ui;padding:40px'>pngquant binary not found.<br>Bundle it, or run with <code>--pngquant PATH</code>.</body>")
        webview.start()
        return
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # free port, no clashes
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = Api()
    api.window = webview.create_window(
        "Didit", f"http://127.0.0.1:{server.server_address[1]}",
        js_api=api, width=1280, height=820, min_size=(720, 480))
    webview.start()  # returns when the window is closed, app exits


if __name__ == "__main__":
    main()

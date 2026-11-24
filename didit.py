#!/usr/bin/env python3
"""Didit: native macOS window around the real pngquant binary.

Dev run:   python3 didit.py [--pngquant PATH]
Build:     pyinstaller Didit.spec   (bundles ./pngquant into the app)
"""
import argparse, base64, os, re, shutil, subprocess, sys, tempfile, threading, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import webview
from webview.dom import DOMEventHandler

SIPS = "/usr/bin/sips"  # built into macOS: converts to PNG and resizes by width
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def find_pngquant(cli_path=None):
    """Use the pngquant shipped with Didit (bundled in the app, or next to this
    file in dev), only falling back to a system install if it is missing."""
    candidates = []
    if cli_path:
        candidates.append(os.path.expanduser(cli_path))
    bundle_dir = getattr(sys, "_MEIPASS", None)  # PyInstaller bundle
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, "pngquant"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pngquant"))
    candidates += ["/opt/homebrew/bin/pngquant", "/usr/local/bin/pngquant"]
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
/* macOS system palette. Toolbar and bottom bar use the window background so
   they merge with the native title bar; previews sit on the content background. */
:root{color-scheme:light dark;
  --window:#ececec;--content:#fff;
  --label:rgba(0,0,0,.85);--label2:rgba(0,0,0,.5);--label3:rgba(0,0,0,.25);
  --sep:rgba(0,0,0,.1);--fill:rgba(0,0,0,.05);--ck:rgba(0,0,0,.045);
  --control:#fff;--control-edge:0 0 0 .5px rgba(0,0,0,.16),0 .5px 1.5px rgba(0,0,0,.1);
  --seg-on:#fff;--accent:#007aff;--red:#ff3b30}
@media(prefers-color-scheme:dark){:root{
  --window:#323232;--content:#1e1e1e;
  --label:rgba(255,255,255,.85);--label2:rgba(255,255,255,.55);--label3:rgba(255,255,255,.25);
  --sep:rgba(255,255,255,.1);--fill:rgba(255,255,255,.08);--ck:rgba(255,255,255,.05);
  --control:rgba(255,255,255,.14);--control-edge:0 0 0 .5px rgba(255,255,255,.05),0 1px 1px rgba(0,0,0,.25);
  --seg-on:rgba(255,255,255,.2);--accent:#0a84ff;--red:#ff453a}}
/* Follow the accent colour chosen in System Settings (WebKit only) */
@supports(color:-apple-system-control-accent){:root{--accent:-apple-system-control-accent}}
:root{--focus:color-mix(in srgb,var(--accent) 50%,transparent)}
@media(prefers-contrast:more){:root{
  --sep:color-mix(in srgb,CanvasText 45%,transparent);
  --label2:color-mix(in srgb,CanvasText 80%,transparent);
  --label3:color-mix(in srgb,CanvasText 55%,transparent)}}

*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;display:flex;flex-direction:column;overflow:hidden;
  font:13px/1.35 -apple-system,BlinkMacSystemFont,system-ui,sans-serif;
  color:var(--label);background:var(--content);
  cursor:default;-webkit-user-select:none;user-select:none;-webkit-font-smoothing:antialiased}
button{font:inherit;color:inherit;cursor:default}
:focus-visible{outline:3px solid var(--focus);outline-offset:1px}
:focus:not(:focus-visible){outline:none}

/* Toolbar */
.toolbar{flex:none;display:flex;align-items:center;gap:16px;flex-wrap:wrap;min-height:52px;padding:8px 12px;
  background:var(--window);border-bottom:1px solid var(--sep)}
.tb-btn{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 9px;border:0;border-radius:6px;background:none}
.tb-btn svg{color:var(--label2)}
.tb-btn:hover{background:var(--fill)}
.tb-btn:active{background:var(--sep)}
.tb-sep{width:1px;height:20px;background:var(--sep);margin:0 -4px}
.field{display:inline-flex;align-items:center;gap:7px;white-space:nowrap}
.spacer{flex:1}
input[type=range]{width:120px;margin:0;accent-color:var(--accent)}
output{min-width:48px;color:var(--label2);font-variant-numeric:tabular-nums}
input[type=checkbox]{margin:0;width:14px;height:14px;accent-color:var(--accent)}
.textfield{display:inline-flex;align-items:center;height:22px;padding:0 7px;border-radius:5px;
  background:var(--control);box-shadow:var(--control-edge)}
.textfield:focus-within{box-shadow:var(--control-edge),0 0 0 3px var(--focus)}
.textfield input{width:46px;padding:0;border:0;outline:none;background:none;font:inherit;color:var(--label);
  text-align:right;font-variant-numeric:tabular-nums;-webkit-user-select:text;user-select:text}
.textfield input::placeholder{color:var(--label3)}
.textfield input::-webkit-inner-spin-button{display:none}
.unit{margin-left:3px;color:var(--label2)}

/* Segmented control */
.segmented{display:inline-flex;gap:2px;padding:2px;border-radius:7px;background:var(--fill)}
.segmented button{height:22px;padding:0 10px;border:0;border-radius:5px;background:none}
.segmented button[aria-pressed=true]{background:var(--seg-on);box-shadow:0 .5px 1.5px rgba(0,0,0,.18),0 0 0 .5px rgba(0,0,0,.05)}

/* Push buttons */
.push{height:24px;padding:0 12px;border:0;border-radius:6px;white-space:nowrap;
  background:var(--control);box-shadow:var(--control-edge)}
.push:active:not(:disabled){filter:brightness(.9)}
.push.primary{color:#fff;background:var(--accent);
  background-image:linear-gradient(rgba(255,255,255,.16),rgba(255,255,255,0));box-shadow:0 .5px 1.5px rgba(0,0,0,.22)}
.push:disabled{opacity:.45}

/* Content */
main{flex:1;min-height:0;overflow:auto;background:var(--content)}
body.dragover main{outline:3px solid var(--accent);outline-offset:-3px}

/* Empty state */
#drop{height:100%;display:flex;align-items:center;justify-content:center;padding:24px}
.well{width:min(520px,100%);padding:48px 32px;display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center;
  border:2px dashed var(--label3);border-radius:14px;transition:border-color .15s,background-color .15s}
.well svg{color:var(--label3);margin-bottom:8px}
.well h1{margin:0;font-size:17px;font-weight:600;letter-spacing:-.01em}
.well p{margin:0 0 12px;color:var(--label2)}
.dragover .well{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 7%,transparent)}
.dragover .well svg{color:var(--accent)}
body.has-files #drop,body:not(.has-files) #file-list,body:not(.has-files) #bar{display:none}

/* Files */
#file-list{display:flex;flex-direction:column;gap:28px;padding:18px 20px 28px}
.file-head{display:flex;align-items:baseline;gap:10px;min-width:0;margin:0 2px 10px}
.file-name{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.file-meta{flex:none;color:var(--label2);font-variant-numeric:tabular-nums}
.file-meta.err{color:var(--red);flex:1;-webkit-user-select:text;user-select:text}
.file-grid{display:grid;gap:18px 16px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}

/* Preview cards: Photos-style selection ring and check badge */
.card{position:relative;outline:none;transition:transform .1s ease-out}
.card.ready:active{transform:scale(.985)}
.card .im{position:relative;min-height:140px;display:flex;align-items:center;justify-content:center;border-radius:8px;overflow:hidden;
  background:repeating-conic-gradient(var(--ck) 0 25%,transparent 0 50%) 0 0/16px 16px}
.card .im::after{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
  box-shadow:inset 0 0 0 1px var(--sep);transition:box-shadow .12s ease-out}
.card.ready:hover .im::after{box-shadow:inset 0 0 0 1px var(--label3)}
.card:focus-visible .im::after{box-shadow:inset 0 0 0 3px var(--focus)}
.card.selected .im::after{box-shadow:inset 0 0 0 3px var(--accent)}
.card img{display:block;max-width:100%;animation:fade .18s ease-out}
.check{position:absolute;top:8px;right:8px;width:20px;height:20px;border-radius:50%;display:grid;place-items:center;
  color:#fff;background:rgba(0,0,0,.28);box-shadow:0 0 0 1.5px #fff,0 1px 3px rgba(0,0,0,.3);
  opacity:0;transform:scale(.6);transition:opacity .12s ease-out,transform .22s cubic-bezier(.3,1.5,.6,1)}
.check svg{opacity:0}
.card.ready:hover .check{opacity:1;transform:none}
.card.ready.selected .check{opacity:1;transform:none;background:var(--accent)}
.card.selected .check svg{opacity:1}
.cap{display:flex;justify-content:space-between;align-items:baseline;gap:8px;padding:7px 2px 0}
.cap .title{font-weight:500}
.cap .meta{color:var(--label2);font-variant-numeric:tabular-nums;white-space:nowrap}
.cap .saving{color:var(--label)}
.im .err{padding:12px;font-size:12px;color:var(--red);-webkit-user-select:text;user-select:text}
.spinner{width:18px;height:18px;border-radius:50%;border:2px solid var(--sep);border-top-color:var(--label2);animation:spin .8s linear infinite}

/* Actual Size: one card per row, image at its natural size, scroll if wider */
.zoomed .card{grid-column:1/-1}
.zoomed .card .im{min-height:auto;overflow:auto;justify-content:flex-start}
.zoomed .card img{max-width:none;flex:none}

/* Bottom bar */
#bar{flex:none;display:flex;align-items:center;gap:12px;height:44px;padding:0 12px;
  background:var(--window);border-top:1px solid var(--sep)}
#stat{flex:1;min-width:0;color:var(--label2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}

@keyframes spin{to{transform:rotate(1turn)}}
@keyframes fade{from{opacity:0}}
@media(prefers-reduced-motion:reduce){
  .card,.check,.card .im::after,.well{transition:none}
  .card.ready:active{transform:none}
  .check{transform:none!important}
  .card img{animation:none}
  .spinner{animation-duration:2.4s}}
</style>

<header class=toolbar>
 <button class=tb-btn id=open title="Open images (⌘O)">
  <svg width=18 height=18 viewBox="0 0 20 20" fill=none stroke=currentColor stroke-width=1.5 stroke-linejoin=round aria-hidden=true><path d="M2.5 5.5a1.5 1.5 0 0 1 1.5-1.5h3.6l1.8 2h6.6a1.5 1.5 0 0 1 1.5 1.5v7a1.5 1.5 0 0 1-1.5 1.5H4a1.5 1.5 0 0 1-1.5-1.5z"/></svg>
  <span>Open…</span>
 </button>
 <span class=tb-sep></span>
 <label class=field>Colors <input id=s type=range min=2 max=253 value=2> <output id=sv for=s>2–5</output></label>
 <label class=field>Width <span class=textfield><input id=w type=number min=1 max=10000 value=1200 placeholder=Original><span class=unit>px</span></span></label>
 <label class=field><input id=dither type=checkbox checked> Dithering</label>
 <span class=spacer></span>
 <div class=segmented role=group aria-label=Zoom>
  <button id=fit aria-pressed=true title="Zoom to Fit (⌘9)">Fit</button>
  <button id=actual aria-pressed=false title="Actual Size (⌘0)">Actual Size</button>
 </div>
</header>

<main>
 <div id=drop>
  <div class=well>
   <svg width=52 height=52 viewBox="0 0 52 52" fill=none stroke=currentColor stroke-width=2 stroke-linejoin=round aria-hidden=true><rect x=6 y=10 width=40 height=32 rx=5 /><circle cx=18 cy=21 r=3.5 /><path d="M6 36l11-10 8 7 7-6 14 12"/></svg>
   <h1>Drop Images Here</h1>
   <p>Compare color reductions side by side, then save the ones you like.</p>
   <button class=push id=open2>Open…</button>
  </div>
  <input id=f type=file accept="image/*" multiple hidden>
 </div>
 <div id=file-list></div>
</main>

<footer id=bar>
 <button class=push id=sel-all>Select All</button>
 <span id=stat></span>
 <button class="push primary" id=save disabled title="Save selected (⌘S)">Save</button>
</footer>

<script>
const $=i=>document.getElementById(i);
const CHECK='<svg width=12 height=12 viewBox="0 0 16 16" aria-hidden=true><path d="M3.5 8.5l3 3 6-7" fill=none stroke=currentColor stroke-width=2.2 stroke-linecap=round stroke-linejoin=round /></svg>';
let files=[],timer=0;
const isApp=()=>!!(window.pywebview&&window.pywebview.api);
const fmt=b=>b>1048576?(b/1048576).toFixed(2)+' MB':(b/1024).toFixed(1)+' KB';
const plural=(n,w)=>n+' '+w+(n===1?'':'s');

// Zoom: segmented control, ⌘9 / ⌘0 like Preview
function setZoom(actual){
  document.body.classList.toggle('zoomed',actual);
  $('fit').setAttribute('aria-pressed',!actual);
  $('actual').setAttribute('aria-pressed',actual);
}
$('fit').onclick=()=>setZoom(false);
$('actual').onclick=()=>setZoom(true);

// Selection
const readyCards=()=>[...document.querySelectorAll('.card.ready')];
const selectedCards=()=>[...document.querySelectorAll('.card.selected')];
function setSelected(card,on){
  card.classList.toggle('selected',on);
  card.setAttribute('aria-checked',on);
}
function selectAll(on){readyCards().forEach(c=>setSelected(c,on));updateBar()}
$('sel-all').onclick=()=>{const n=selectedCards().length;selectAll(!(n&&n===readyCards().length))};

// Bottom bar reflects the selection; a message (e.g. after saving) replaces the count until it changes
function updateBar(msg){
  const n=selectedCards().length,total=readyCards().length;
  const save=$('save');
  save.disabled=!n||save.dataset.busy==='1';
  if(save.dataset.busy!=='1') save.textContent=isApp()?(n?`Save ${n} to didit/`:'Save to didit/'):(n?`Download ${n}`:'Download');
  $('sel-all').textContent=n&&n===total?'Deselect All':'Select All';
  $('sel-all').disabled=!total;
  $('stat').textContent=msg??(n?`${n} of ${plural(total,'preview')} selected`:total?plural(total,'preview'):'');
  if(msg===undefined) $('stat').title='';
}

const toB64=blob=>new Promise(r=>{const fr=new FileReader();fr.onload=()=>r(fr.result.split(',')[1]);fr.readAsDataURL(blob)});

// Save every selected preview into a "didit" folder next to its original, no prompt
async function saveSelected(){
  const sel=selectedCards();
  const save=$('save');
  if(!sel.length||save.dataset.busy==='1')return;
  const items=sel.map(c=>{
    const fileIdx=+c.dataset.fileIdx,width=+c.dataset.width;
    const name=files[fileIdx].name.replace(/\\.[^.]+$/,'')+'-'+c.dataset.colors+(width?'-w'+width:'')+'.png';
    return {src:files[fileIdx].name,name,blob:c._blob};
  });
  save.dataset.busy='1';save.disabled=true;save.textContent='Saving…';
  let msg;
  try{
    if(isApp()){
      const payload=await Promise.all(items.map(async({src,name,blob})=>({src,name,b64:await toB64(blob)})));
      const r=await pywebview.api.save_all(payload);
      const where=r.folders.length===1?r.folders[0]:plural(r.folders.length,'didit folder');
      msg=r.saved===items.length?`Saved ${plural(r.saved,'image')} to ${where}`
        :`Saved ${r.saved} of ${plural(items.length,'image')}. The rest couldn't be written.`;
      $('stat').title=r.folders.join('\\n');
    }else{
      items.forEach(({name,blob})=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click()});
      msg=`Downloaded ${plural(items.length,'image')}`;
    }
  }catch(e){msg="Couldn't save: "+(e&&e.message||e)}
  save.dataset.busy='0';
  updateBar(msg);
}
$('save').onclick=saveSelected;

// Opening files
async function openFiles(){
  if(!isApp()) return $('f').click();
  const picked=await pywebview.api.open_files();
  if(!picked||!picked.length) return;
  load(await Promise.all(picked.map(async({name,id})=>new File([await (await fetch('/file?id='+id)).blob()],name))));
}
$('open').onclick=openFiles;
$('open2').onclick=openFiles;
$('f').oninput=e=>{if(e.target.files.length)load([...e.target.files]);e.target.value=''};

// Drag & drop anywhere in the window; the content area highlights as the drop target
let dragDepth=0;
const endDrag=()=>{dragDepth=0;document.body.classList.remove('dragover')};
document.addEventListener('dragenter',e=>{e.preventDefault();dragDepth++;document.body.classList.add('dragover')});
document.addEventListener('dragleave',()=>{if(--dragDepth<=0)endDrag()});
document.addEventListener('dragover',e=>e.preventDefault());
document.addEventListener('drop',e=>{e.preventDefault();endDrag();load([...e.dataTransfer.files])});

function load(newFiles){
  if(!newFiles||!newFiles.length)return;
  files=[...newFiles];
  document.body.classList.add('has-files');
  renderFileList();
}

function renderFileList(){
  const list=$('file-list');
  list.innerHTML='';
  files.forEach((file,i)=>{
    const section=document.createElement('section');
    section.innerHTML=`<div class=file-head><span class=file-name></span><span class=file-meta id=file-status-${i}></span></div><div class=file-grid id=file-grid-${i}></div>`;
    const name=section.querySelector('.file-name');
    name.textContent=file.name;name.title=file.name;
    list.appendChild(section);
  });
  files.forEach((f,i)=>processFile(f,i));
}

// Click toggles a preview (pressed state shows on mouse-down); Space toggles the focused one
$('file-list').addEventListener('click',e=>{
  const card=e.target.closest('.card.ready');
  if(!card||e.target.closest('.err'))return;
  setSelected(card,!card.classList.contains('selected'));updateBar();
});
$('file-list').addEventListener('keydown',e=>{
  const card=e.target.closest('.card.ready');
  if(card&&(e.key===' '||e.key==='Enter')){e.preventDefault();setSelected(card,!card.classList.contains('selected'));updateBar()}
});

const runs={};  // latest run id per file, so stale results are dropped
async function processFile(file,fileIdx){
  if(!file)return;
  const run=runs[fileIdx]=(runs[fileIdx]||0)+1;
  const stale=()=>runs[fileIdx]!==run;
  const grid=$(`file-grid-${fileIdx}`),status=$(`file-status-${fileIdx}`);
  grid.innerHTML='';
  status.className='file-meta';
  status.textContent=fmt(file.size)+' · Preparing…';
  updateBar();

  const w=Math.max(0,parseInt($('w').value)||0);
  const start=Math.max(2,Math.min(253,parseInt($('s').value)||2));
  const ext=(file.name.split('.').pop()||'png').toLowerCase();
  const nofs=$('dither').checked?0:1;

  // Placeholders straight away, so the layout doesn't jump when results arrive
  const cards=Array.from({length:4},(_,i)=>{
    const n=start+i,card=document.createElement('div');
    card.className='card';card.dataset.fileIdx=fileIdx;card.dataset.colors=n;card.dataset.width=w;
    card.setAttribute('role','checkbox');card.setAttribute('aria-checked','false');
    card.innerHTML=`<div class=im><span class=spinner></span></div><span class=check>${CHECK}</span><div class=cap><span class=title>${n} colors</span><span class=meta></span></div>`;
    grid.appendChild(card);
    return card;
  });

  const pr=await fetch('/prepare?'+new URLSearchParams({width:w,ext,fileIdx}),{method:'POST',body:file});
  if(stale())return;
  if(!pr.ok){
    status.className='file-meta err';status.textContent=await pr.text();
    grid.innerHTML='';return;
  }
  const src=await pr.blob();
  const bmp=await createImageBitmap(src);
  if(stale()){bmp.close();return}
  status.textContent=`${fmt(file.size)} · ${bmp.width}×${bmp.height} PNG, ${fmt(src.size)} before quantizing`;
  bmp.close();

  await Promise.all(cards.map(async card=>{
    const im=card.querySelector('.im'),meta=card.querySelector('.meta');
    const res=await fetch('/quantize?'+new URLSearchParams({colors:card.dataset.colors,nofs,fileIdx}),{method:'POST',body:src});
    if(stale())return;
    if(!res.ok){
      meta.textContent='Failed';
      im.innerHTML='<p class=err></p>';im.firstChild.textContent=await res.text();
      return;
    }
    const blob=await res.blob();
    if(stale())return;
    const img=new Image();
    img.alt=card.dataset.colors+' colors';
    img.src=URL.createObjectURL(blob);
    await img.decode().catch(()=>{});
    if(stale())return;
    im.replaceChildren(img);
    const pct=Math.round((1-blob.size/src.size)*100);
    meta.innerHTML='';
    meta.append(fmt(blob.size)+' ');
    const d=document.createElement('span');
    d.className=pct>0?'saving':'';d.textContent=pct>0?`−${pct}%`:`+${-pct}%`;
    meta.append(d);
    card._blob=blob;card.tabIndex=0;card.classList.add('ready');
    updateBar();
  }));
}

// Settings re-run every file after a short pause
const showRange=()=>{const v=parseInt($('s').value);$('sv').textContent=`${v}–${v+3}`};
['s','w','dither'].forEach(i=>$(i).oninput=()=>{
  showRange();
  if(files.length){clearTimeout(timer);timer=setTimeout(()=>files.forEach((f,idx)=>processFile(f,idx)),400)}
});
showRange();

// Keyboard shortcuts
document.addEventListener('keydown',e=>{
  if(!e.metaKey){if(e.key==='Escape'&&files.length)selectAll(false);return}
  const k=e.key.toLowerCase(),inField=e.target.matches('input[type=number]');
  if(k==='o'){e.preventDefault();openFiles()}
  else if(k==='s'){e.preventDefault();saveSelected()}
  else if(k==='a'&&!inField&&files.length){e.preventDefault();selectAll(true)}
  else if(k==='0'){e.preventDefault();setZoom(true)}
  else if(k==='9'){e.preventDefault();setZoom(false)}
});
window.addEventListener('pywebviewready',()=>updateBar());
updateBar();
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
        url = urlparse(self.path)
        if url.path == "/file":
            # Only files the user picked in the open dialog
            path = API._opened.get(parse_qs(url.query).get("id", [""])[0])
            if not path:
                return self._send(404, b"not found")
            with open(path, "rb") as fh:
                return self._send(200, fh.read(), "application/octet-stream")
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
            # No -v: pngquant 3.x prints its verbose log to stdout when the
            # output is stdout, which would be prepended to the PNG bytes.
            cmd = [PNGQUANT, str(colors)]
            if q.get("nofs", ["0"])[0] == "1":
                cmd.append("--nofs")
            cmd.append("-")  # stdin -> stdout
            p = subprocess.run(cmd, input=data, capture_output=True)
            if p.returncode != 0:
                msg = p.stderr.decode(errors="replace") or f"pngquant exit {p.returncode}"
                return self._send(500, msg.encode())
            if not p.stdout.startswith(PNG_SIGNATURE):
                return self._send(500, b"pngquant did not return a valid PNG")
            return self._send(200, p.stdout, "image/png")

        self._send(404, b"not found")


class Api:
    """Exposed to the page as window.pywebview.api"""

    def __init__(self):
        self.window = None
        self._sources = {}  # original file name -> full path (from drop or open dialog)
        self._opened = {}   # id -> full path, served by GET /file

    def _remember_drop(self, event):
        for f in event.get("dataTransfer", {}).get("files", []):
            if f.get("pywebviewFullPath"):
                self._sources[f["name"]] = f["pywebviewFullPath"]

    def open_files(self):
        open_type = webview.FileDialog.OPEN if hasattr(webview, "FileDialog") else webview.OPEN_DIALOG
        result = self.window.create_file_dialog(open_type, allow_multiple=True)
        picked = []
        for path in result or []:
            name = os.path.basename(path)
            self._sources[name] = path
            file_id = str(len(self._opened))
            self._opened[file_id] = path
            picked.append({"name": name, "id": file_id})
        return picked

    def save_all(self, items):
        """Write each item into a "didit" folder next to its original image,
        overwriting without asking. Falls back to ~/Downloads/didit when the
        original's location is unknown."""
        fallback = os.path.join(os.path.expanduser("~/Downloads"), "didit")
        saved, folders = 0, []
        for item in items:
            src = self._sources.get(item["src"])
            folder = os.path.join(os.path.dirname(src), "didit") if src else fallback
            try:
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, os.path.basename(item["name"])), "wb") as fh:
                    fh.write(base64.b64decode(item["b64"]))
            except OSError:
                continue
            saved += 1
            if folder not in folders:
                folders.append(folder)
        return {"saved": saved, "folders": folders}


API = Api()


def main():
    if not PNGQUANT:
        webview.create_window("Didit", html="<body style='font:16px system-ui;padding:40px'>pngquant binary not found.<br>Bundle it, or run with <code>--pngquant PATH</code>.</body>")
        webview.start()
        return
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)  # free port, no clashes
    threading.Thread(target=server.serve_forever, daemon=True).start()
    window = API.window = webview.create_window(
        "Didit", f"http://127.0.0.1:{server.server_address[1]}",
        js_api=API, width=1280, height=820, min_size=(760, 480),
        background_color="#ECECEC")

    def on_loaded():
        # A Python drop listener makes pywebview attach each dropped file's full path
        window.dom.document.events.drop += DOMEventHandler(API._remember_drop)

    window.events.loaded += on_loaded
    webview.start()  # returns when the window is closed, app exits


if __name__ == "__main__":
    main()

from pathlib import Path

path = Path('/Users/vince/sTIMulation/templates/index.html')
text = path.read_text()

old_zoom = """const MIN_SCALE = 1.0;
const MAX_SCALE = 2.0;   /* Updated: 100% max zoom-in */

let CAM = { x:0, y:0, scale:1 };

function resetView() { CAM = { x:0, y:0, scale:1 }; }

function resize() {
  canvas.width  = wrap.clientWidth;
  canvas.height = wrap.clientHeight;
  CAM.scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, CAM.scale));
}
resize();
window.addEventListener('resize', resize);

/* Button zoom — center-anchored, strictly bounded */
function zoomAt(factor) {
  const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, CAM.scale * factor));
  if (newScale === CAM.scale) return;
  const cx = canvas.width / 2, cy = canvas.height / 2;
  const r  = newScale / CAM.scale;
  CAM.x     = cx - r * (cx - CAM.x);
  CAM.y     = cy - r * (cy - CAM.y);
  CAM.scale = newScale;
}

document.getElementById('btn-zoom-in').addEventListener('click',  () => zoomAt(1.10));
document.getElementById('btn-zoom-out').addEventListener('click', () => zoomAt(0.91));

/* Block ALL other zoom/gesture/pan input */
['wheel','touchstart','touchmove','touchend','gesturestart','gesturechange','gestureend'].forEach(evt =>
  canvas.addEventListener(evt, e => e.preventDefault(), { passive:false })
);
canvas.addEventListener('contextmenu', e => e.preventDefault());
"""

new_zoom = """const MIN_SCALE = 0.3;
const MAX_SCALE = 5.0;

let CAM = { x:0, y:0, scale:1 };

function resetView() { CAM = { x:0, y:0, scale:1 }; }

function resize() {
  canvas.width  = wrap.clientWidth;
  canvas.height = wrap.clientHeight;
  CAM.scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, CAM.scale));
}
resize();
window.addEventListener('resize', resize);

function zoomAt(factor, focusX=canvas.width/2, focusY=canvas.height/2) {
  const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, CAM.scale * factor));
  if (newScale === CAM.scale) return;
  const r  = newScale / CAM.scale;
  CAM.x    = focusX - r * (focusX - CAM.x);
  CAM.y    = focusY - r * (focusY - CAM.y);
  CAM.scale = newScale;
}

document.getElementById('btn-zoom-in').addEventListener('click',  () => zoomAt(1.10));
document.getElementById('btn-zoom-out').addEventListener('click', () => zoomAt(0.91));

canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const focusX = e.clientX - rect.left;
  const focusY = e.clientY - rect.top;
  const factor = e.deltaY < 0 ? 1.08 : 0.92;
  zoomAt(factor, focusX, focusY);
}, { passive:false });

['touchstart','touchmove','touchend','gesturestart','gesturechange','gestureend'].forEach(evt =>
  canvas.addEventListener(evt, e => e.preventDefault(), { passive:false })
);
canvas.addEventListener('contextmenu', e => e.preventDefault());
"""

if old_zoom not in text:
    raise SystemExit('zoom block not found')
text = text.replace(old_zoom, new_zoom)

old_head = """function drawVehicle(x,y,angle,color,state,alpha=1,vid){ctx.save();ctx.globalAlpha=alpha;ctx.translate(x,y);ctx.rotate(angle-Math.PI/2);const carSprite=vid%2===0?CAR1_SPRITE:CAR2_SPRITE,carReady=vid%2===0?CAR1_READY:CAR2_READY;if(carReady&&carSprite.naturalWidth>0){const spriteH=24,ratio=carSprite.naturalWidth/carSprite.naturalHeight||1,spriteW=spriteH*ratio;ctx.shadowColor='rgba(0,0,0,.4)';ctx.shadowBlur=4;ctx.shadowOffsetY=2;ctx.drawImage(carSprite,-spriteW/2,-spriteH/2,spriteW,spriteH);ctx.shadowBlur=0;if(state==='moving'){ctx.fillStyle='#fffacd';ctx.globalAlpha=alpha*.85;ctx.beginPath();ctx.arc(-4,-spriteH/2-3,2,0,Math.PI*2);ctx.fill();ctx.beginPath();ctx.arc(4,-spriteH/2-3,2,0,Math.PI*2);ctx.fill();ctx.globalAlpha=alpha;ctx.fillStyle='rgba(255,250,205,.08)';ctx.beginPath();ctx.moveTo(-spriteW/2,-spriteH/2);ctx.lineTo(-spriteW/2-20,-spriteH/2-18);ctx.lineTo(-spriteW/2-20,-spriteH/2+18);ctx.closePath();ctx.fill();ctx.beginPath();ctx.moveTo(spriteW/2,-spriteH/2);ctx.lineTo(spriteW/2+20,-spriteH/2-18);ctx.lineTo(spriteW/2+20,-spriteH/2+18);ctx.closePath();ctx.fill();}}else{ctx.shadowColor='rgba(0,0,0,.55)';ctx.shadowBlur=6;ctx.shadowOffsetY=3;ctx.fillStyle=color;roundRect(-9,-5.5,18,11,2.5);ctx.fill();ctx.shadowBlur=0;ctx.shadowOffsetY=0;ctx.fillStyle=color+'cc';roundRect(-5,-4,9,8,2);ctx.fill();ctx.fillStyle='rgba(200,230,255,.35)';roundRect(-5,-3.5,7,7,1.5);ctx.fill();ctx.fillStyle='rgba(200,230,255,.2)';roundRect(4,-3,3.5,6,1);ctx.fill();if(state==='moving'){ctx.fillStyle='#ffffc0dd';roundRect(-9.5,-4,3,2.5,1);ctx.fill();roundRect(-9.5,1.5,3,2.5,1);ctx.fill();ctx.fillStyle='rgba(255,255,180,.06)';ctx.beginPath();ctx.moveTo(-9,0);ctx.lineTo(-45,-14);ctx.lineTo(-45,14);ctx.closePath();ctx.fill();}else{ctx.fillStyle='#ff3333cc';roundRect(7,-4,2.5,2.5,.8);ctx.fill();roundRect(7,1.5,2.5,2.5,.8);ctx.fill();}}ctx.restore();}
"""

new_head = """function drawVehicle(x,y,angle,color,state,alpha=1,vid){ctx.save();ctx.globalAlpha=alpha;ctx.translate(x,y);ctx.rotate(angle-Math.PI/2);const carSprite=vid%2===0?CAR1_SPRITE:CAR2_SPRITE,carReady=vid%2===0?CAR1_READY:CAR2_READY;if(carReady&&carSprite.naturalWidth>0){const spriteH=24,ratio=carSprite.naturalWidth/carSprite.naturalHeight||1,spriteW=spriteH*ratio;ctx.shadowColor='rgba(0,0,0,.4)';ctx.shadowBlur=4;ctx.shadowOffsetY=2;ctx.drawImage(carSprite,-spriteW/2,-spriteH/2,spriteW,spriteH);ctx.shadowBlur=0;if(state==='moving'){const frontY=-spriteH/2-2;ctx.fillStyle='#fffacd';ctx.globalAlpha=alpha*.9;ctx.beginPath();ctx.arc(-4,frontY,2.2,0,Math.PI*2);ctx.fill();ctx.beginPath();ctx.arc(4,frontY,2.2,0,Math.PI*2);ctx.fill();ctx.globalAlpha=alpha;ctx.fillStyle='rgba(255,250,205,.10)';ctx.beginPath();ctx.moveTo(-4,frontY+1);ctx.quadraticCurveTo(-22,frontY-8,-46,frontY-18);ctx.lineTo(-46,frontY+12);ctx.quadraticCurveTo(-22,frontY+10,-4,frontY+4);ctx.closePath();ctx.fill();ctx.beginPath();ctx.moveTo(4,frontY+1);ctx.quadraticCurveTo(22,frontY-8,46,frontY-18);ctx.lineTo(46,frontY+12);ctx.quadraticCurveTo(22,frontY+10,4,frontY+4);ctx.closePath();ctx.fill();ctx.fillStyle='rgba(255,250,205,.22)';ctx.beginPath();ctx.arc(0,frontY+2,13,0,Math.PI*2);ctx.fill();}}else{ctx.shadowColor='rgba(0,0,0,.55)';ctx.shadowBlur=6;ctx.shadowOffsetY=3;ctx.fillStyle=color;roundRect(-9,-5.5,18,11,2.5);ctx.fill();ctx.shadowBlur=0;ctx.shadowOffsetY=0;ctx.fillStyle=color+'cc';roundRect(-5,-4,9,8,2);ctx.fill();ctx.fillStyle='rgba(200,230,255,.35)';roundRect(-5,-3.5,7,7,1.5);ctx.fill();ctx.fillStyle='rgba(200,230,255,.2)';roundRect(4,-3,3.5,6,1);ctx.fill();if(state==='moving'){ctx.fillStyle='#ffffc0dd';roundRect(-9.5,-4,3,2.5,1);ctx.fill();roundRect(-9.5,1.5,3,2.5,1);ctx.fill();ctx.fillStyle='rgba(255,255,180,.06)';ctx.beginPath();ctx.moveTo(-9,0);ctx.lineTo(-45,-14);ctx.lineTo(-45,14);ctx.closePath();ctx.fill();}else{ctx.fillStyle='#ff3333cc';roundRect(7,-4,2.5,2.5,.8);ctx.fill();roundRect(7,1.5,2.5,2.5,.8);ctx.fill();}}ctx.restore();}
"""

if old_head not in text:
    raise SystemExit('drawVehicle block not found')
text = text.replace(old_head, new_head)

path.write_text(text)
print('patched headlights and zoom')

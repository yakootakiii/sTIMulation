from pathlib import Path

path = Path('/Users/vince/sTIMulation/templates/index.html')
text = path.read_text()

old_load = """const CAT_SPRITE=new Image();CAT_SPRITE.src='/assets/Cat_nobg.png';let CAT_READY=false;CAT_SPRITE.onload=()=>{CAT_READY=true;};CAT_SPRITE.onerror=()=>{CAT_READY=false;};const CAR1_SPRITE=new Image();CAR1_SPRITE.src='/assets/Car1-removebg-preview.png';let CAR1_READY=false;CAR1_SPRITE.onload=()=>{CAR1_READY=true;};CAR1_SPRITE.onerror=()=>{CAR1_READY=false;};const CAR2_SPRITE=new Image();CAR2_SPRITE.src='/assets/Car2_Nobg.png';let CAR2_READY=false;CAR2_SPRITE.onload=()=>{CAR2_READY=true;};CAR2_SPRITE.onerror=()=>{CAR2_READY=false;};"""
new_load = """const CAT_FRAMES=Array.from({length:10},(_,i)=>new Image());const CAT_READY=Array(10).fill(false);CAT_FRAMES.forEach((img,idx)=>{img.src=`/assets/cat${idx+1}.png`;img.onload=()=>{CAT_READY[idx]=true;};img.onerror=()=>{CAT_READY[idx]=false;};});const CAR_SPRITES=[new Image(),new Image(),new Image()];const CAR_READY=[false,false,false];['/assets/Car_01.png','/assets/Car_02.png','/assets/Car_03.png'].forEach((src,idx)=>{CAR_SPRITES[idx].src=src;CAR_SPRITES[idx].onload=()=>{CAR_READY[idx]=true;};CAR_SPRITES[idx].onerror=()=>{CAR_READY[idx]=false;};});"""
if old_load not in text:
    raise SystemExit('sprite loading block not found')
text = text.replace(old_load, new_load)

old_draw = """function drawVehicle(x,y,angle,color,state,alpha=1,vid){ctx.save();ctx.globalAlpha=alpha;ctx.translate(x,y);ctx.rotate(angle-Math.PI/2);const carSprite=vid%2===0?CAR1_SPRITE:CAR2_SPRITE,carReady=vid%2===0?CAR1_READY:CAR2_READY;if(carReady&&carSprite.naturalWidth>0){const spriteH=24,ratio=carSprite.naturalWidth/carSprite.naturalHeight||1,spriteW=spriteH*ratio;ctx.drawImage(carSprite,-spriteW/2,-spriteH/2,spriteW,spriteH);}else{ctx.fillStyle=color;roundRect(-9,-5.5,18,11,2.5);ctx.fill();ctx.fillStyle=color+'cc';roundRect(-5,-4,9,8,2);ctx.fill();ctx.fillStyle='rgba(200,230,255,.35)';roundRect(-5,-3.5,7,7,1.5);ctx.fill();ctx.fillStyle='rgba(200,230,255,.2)';roundRect(4,-3,3.5,6,1);ctx.fill();if(state==='moving'){ctx.fillStyle='#ffffc0dd';roundRect(-9.5,-4,3,2.5,1);ctx.fill();roundRect(-9.5,1.5,3,2.5,1);ctx.fill();ctx.fillStyle='rgba(255,255,180,.06)';ctx.beginPath();ctx.moveTo(-9,0);ctx.lineTo(-45,-14);ctx.lineTo(-45,14);ctx.closePath();ctx.fill();}else{ctx.fillStyle='#ff3333cc';roundRect(7,-4,2.5,2.5,.8);ctx.fill();roundRect(7,1.5,2.5,2.5,.8);ctx.fill();}}ctx.restore();}"""
new_draw = """function drawVehicle(x,y,angle,color,state,alpha=1,vid){ctx.save();ctx.globalAlpha=alpha;ctx.translate(x,y);ctx.rotate(angle-Math.PI/2);const spriteIdx=vid%CAR_SPRITES.length,carSprite=CAR_SPRITES[spriteIdx],carReady=CAR_READY[spriteIdx];if(carReady&&carSprite.naturalWidth>0){const spriteH=24,ratio=carSprite.naturalWidth/carSprite.naturalHeight||1,spriteW=spriteH*ratio;ctx.drawImage(carSprite,-spriteW/2,-spriteH/2,spriteW,spriteH);}else{ctx.fillStyle=color;roundRect(-9,-5.5,18,11,2.5);ctx.fill();ctx.fillStyle=color+'cc';roundRect(-5,-4,9,8,2);ctx.fill();ctx.fillStyle='rgba(200,230,255,.35)';roundRect(-5,-3.5,7,7,1.5);ctx.fill();ctx.fillStyle='rgba(200,230,255,.2)';roundRect(4,-3,3.5,6,1);ctx.fill();if(state==='moving'){ctx.fillStyle='#ffffc0dd';roundRect(-9.5,-4,3,2.5,1);ctx.fill();roundRect(-9.5,1.5,3,2.5,1);ctx.fill();ctx.fillStyle='rgba(255,255,180,.06)';ctx.beginPath();ctx.moveTo(-9,0);ctx.lineTo(-45,-14);ctx.lineTo(-45,14);ctx.closePath();ctx.fill();}else{ctx.fillStyle='#ff3333cc';roundRect(7,-4,2.5,2.5,.8);ctx.fill();roundRect(7,1.5,2.5,2.5,.8);ctx.fill();}}ctx.restore();}"""
if old_draw not in text:
    raise SystemExit('drawVehicle block not found')
text = text.replace(old_draw, new_draw)

path.write_text(text)
print('swapped car sprites to Car_01..03')

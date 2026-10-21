
// Runtime adaptation of docs/brand/gongjing-mascot-v1/animation/mascot-rig.js.
import * as THREE from 'three';
export const STATES=['idle','focus','think','verify','done','rest'];
export const DURATION=4;
const TAU=Math.PI*2;
const blink=(p,c,n=110)=>Math.pow((1+Math.cos(p-TAU*c/4))/2,n);
export function poseAt(time,state='idle'){
 const p=TAU*((time%4+4)%4)/4,s=(shift=0,h=1)=>Math.sin(p*h+shift);
 const q={headX:.012*s(),headY:-.007*s(.35),tilt:.025*s(.3),neck:.008*s(-.65),breath:s(),tail:.012*s(-1),pulse:.5+.5*s(-.3),eyeOpen:1-.96*blink(p,1.35),smile:0,rays:0,squash:0};
 if(state==='focus')Object.assign(q,{headX:.035+.022*s(),headY:-.012-.012*s(.35),tilt:-.045+.030*s(.3),neck:.013*s(-.6),eyeOpen:.91-.86*blink(p,2.4,150),rays:.22+.16*s(-.4),pulse:.55+.35*s(0,2)});
 if(state==='think')Object.assign(q,{headX:.025*s(-.15),headY:.018+.012*s(.4,2),tilt:.07+.095*s(-.15),neck:.014*s(-.8),eyeOpen:.73-.67*blink(p,1.85,70),tail:.017*s(-1.2),pulse:.35+.18*s()});
 if(state==='verify')Object.assign(q,{headX:.045*s(),headY:-.012*s(.3,2),tilt:-.075*s(.2),neck:.018*s(-.5),eyeOpen:1-.96*blink(p,3.4,140),rays:.48+.27*s(-.5,2),pulse:.5+.5*s(-.5,2),tail:.017*s(-.9)});
 if(state==='done')Object.assign(q,{headX:.008*s(),headY:-.032+.025*s(-.2,2)+.008*s(-.4,3),tilt:-.065+.035*s(-.45,2),neck:.010*s(-.65,2),tail:.023*s(-.9,2),eyeOpen:1,smile:1,rays:.58+.25*s(-.45,2),pulse:.7+.3*s(-.45,2),squash:.01*s(-.7,2)});
 if(state==='rest')Object.assign(q,{headX:-.018+.006*s(),headY:.105+.009*s(.35),tilt:.15+.018*s(.4),neck:.006*s(-.65),tail:.004*s(-1.1),eyeOpen:.035,smile:-1,pulse:.15+.12*s()});
 return q;
}
const vertexShader=`
precision highp float;
attribute vec3 position;
attribute vec2 uv;
uniform vec2 uHead;
uniform float uTilt,uNeck,uBreath,uTail,uSquash;
varying vec2 vTop;
void main(){
 vec2 q=vec2(uv.x,1.0-uv.y); vTop=q;
 float h=1.0-smoothstep(.25,.74,q.y);
 float coil=smoothstep(.57,.84,q.y);
 float tail=smoothstep(.70,.89,q.x)*smoothstep(.68,.87,q.y);
 vec2 pivot=vec2(.50,.63),d=q-pivot;
 float a=uTilt*h;
 vec2 p=pivot+mat2(cos(a),sin(a),-sin(a),cos(a))*d;
 p+=uHead*h;
 p.x+=uNeck*sin(clamp((.80-q.y)/.65,0.0,1.0)*3.14159265);
 p.x+=(q.x-.50)*.013*uBreath*coil;
 p.y-=(.93-q.y)*(.022*uBreath+uSquash)*coil;
 p.x+=uTail*.18*tail; p.y-=uTail*tail;
 p=(p-vec2(.5))*.90+vec2(.50,.49);
 gl_Position=vec4(p.x*2.0-1.0,1.0-p.y*2.0,0.0,1.0);
}`;
const fragmentShader=`
precision highp float;
uniform sampler2D uTexture;
uniform float uEyeOpen,uSmile,uPulse,uRays;
varying vec2 vTop;
vec4 sampleTop(vec2 p){return texture2D(uTexture,vec2(p.x,1.0-p.y));}
float white(vec3 c){return smoothstep(.45,.78,min(c.r,min(c.g,c.b)));}
float seg(vec2 p,vec2 a,vec2 b){vec2 d=b-a;return length(p-a-d*clamp(dot(p-a,d)/dot(d,d),0.0,1.0));}
void main(){
 vec2 p=vTop; vec4 c=sampleTop(p);
 vec2 eye=vec2(793.51/1254.0,235.58/1254.0);
 float region=(1.0-smoothstep(.052,.064,abs(p.x-eye.x)))*(1.0-smoothstep(.061,.076,abs(p.y-eye.y)));
 float oldEye=max(white(c.rgb),max(max(white(sampleTop(p+vec2(.004,0.)).rgb),white(sampleTop(p-vec2(.004,0.)).rgb)),max(white(sampleTop(p+vec2(0.,.004)).rgb),white(sampleTop(p-vec2(0.,.004)).rgb))))*region*c.a;
 vec3 charcoal=sampleTop(vec2(p.x-.078,p.y)).rgb;
 c.rgb=mix(c.rgb,charcoal,oldEye);
 float opening=max(.025,uEyeOpen);
 vec4 e=sampleTop(vec2(p.x,eye.y+(p.y-eye.y)/opening));
 float eyeMask=white(e.rgb)*region;
 if(abs(uSmile)<.5){c.rgb=mix(c.rgb,e.rgb,eyeMask);}
 else{
  vec2 local=p-eye;float x=local.x/.030;
  float curve=(uSmile>0.0?-.015:.012)*(1.0-x*x);
  float m=(1.0-smoothstep(.0037,.0053,abs(local.y-curve)))*(1.0-smoothstep(.92,1.04,abs(x)))*region;
  c.rgb=mix(c.rgb,vec3(.961,.953,.937),m);
 }
 vec2 status=vec2(929.37/1254.0,207.72/1254.0);
 float lm=(1.0-smoothstep(.020,.025,length(p-status)))*smoothstep(.12,.28,c.g-c.b);
 c.rgb=mix(c.rgb,mix(vec3(.67,.79,.24),vec3(.784,.941,.290),.60+.40*uPulse),lm);
 float r=0.0;
 r=max(r,1.0-smoothstep(.0025,.0040,seg(p,status+vec2(.060,-.043),status+vec2(.082,-.060))));
 r=max(r,1.0-smoothstep(.0025,.0040,seg(p,status+vec2(.069,-.002),status+vec2(.096,-.002))));
 r=max(r,1.0-smoothstep(.0025,.0040,seg(p,status+vec2(.060,.039),status+vec2(.082,.054))));
 r*=uRays;
 gl_FragColor=vec4(c.rgb*c.a*(1.0-r)+vec3(.784,.941,.290)*r,c.a+r*(1.0-c.a));
}`;
export async function createMascot(canvas,{size=768,textureUrl=`${import.meta.env.BASE_URL}brand/mascot-full-body.png`}={}){
 const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,premultipliedAlpha:true,preserveDrawingBuffer:false,powerPreference:'low-power'});
 renderer.setPixelRatio(1);renderer.setSize(size,size,false);renderer.setClearColor(0x000000,0);
 const texture=await new THREE.TextureLoader().loadAsync(textureUrl).catch(error=>{renderer.dispose();throw error});
 texture.colorSpace=THREE.NoColorSpace;texture.minFilter=THREE.LinearFilter;texture.magFilter=THREE.LinearFilter;texture.generateMipmaps=false;
 const uniforms={uTexture:{value:texture},uHead:{value:new THREE.Vector2()},...Object.fromEntries(['Tilt','Neck','Breath','Tail','Squash','EyeOpen','Smile','Pulse','Rays'].map(k=>['u'+k,{value:0}]))};
 const material=new THREE.RawShaderMaterial({uniforms,vertexShader,fragmentShader,transparent:true,depthTest:false,depthWrite:false,premultipliedAlpha:true});
 const mesh=new THREE.Mesh(new THREE.PlaneGeometry(1,1,100,100),material);mesh.frustumCulled=false;
 const scene=new THREE.Scene();scene.add(mesh);const camera=new THREE.Camera();
 function render(t,state='idle',pose=null){
  if(!STATES.includes(state))throw new Error('Unknown mascot state '+state);
  const p=pose||poseAt(t,state);uniforms.uHead.value.set(p.headX,p.headY);
  for(const[k,v]of Object.entries({Tilt:p.tilt,Neck:p.neck,Breath:p.breath,Tail:p.tail,Squash:p.squash,EyeOpen:p.eyeOpen,Smile:p.smile,Pulse:p.pulse,Rays:p.rays}))uniforms['u'+k].value=v;
  renderer.render(scene,camera);return p;
 }
 render(0);
 return{render,renderer,canvas,poseAt,dispose(){mesh.geometry.dispose();material.dispose();texture.dispose();renderer.dispose();renderer.forceContextLoss()}};
}


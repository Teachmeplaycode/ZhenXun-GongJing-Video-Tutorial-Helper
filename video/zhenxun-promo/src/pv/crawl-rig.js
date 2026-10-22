export const CLIPS = {
  'crawl-right': { width:768, height:512, duration:4, label:'向右爬行' },
  'crawl-left': { width:768, height:512, duration:4, label:'向左爬行' },
  patrol: { width:1280, height:720, duration:8, label:'转弯巡游' },
};
const TAU=Math.PI*2;
const smooth=(a,b,x)=>{const v=Math.max(0,Math.min(1,(x-a)/(b-a)));return v*v*(3-2*v)};
const f=v=>Number(v.toFixed(4));
const mod=(x,n)=>(x%n+n)%n;
const N=160;
const path=[];
let pathLength=0;
for(let i=0;i<=1024;i++){
 const a=TAU*i/1024,p={x:640+310*Math.sin(a),y:360+110*Math.cos(a)};
 if(i)pathLength+=Math.hypot(p.x-path[i-1].x,p.y-path[i-1].y);
 path.push({...p,d:pathLength});
}
function along(d){
 d=mod(d,pathLength);
 let lo=0,hi=path.length-1;
 while(hi-lo>1){const m=(lo+hi)>>1;if(path[m].d<d)lo=m;else hi=m}
 const a=path[lo],b=path[hi],u=(d-a.d)/(b.d-a.d);
 return{x:a.x+(b.x-a.x)*u,y:a.y+(b.y-a.y)*u};
}
export function poseAt(time,clip='crawl-right'){
 const spec=CLIPS[clip];if(!spec)throw Error('Unknown clip '+clip);
 const t=mod(time,spec.duration),phase=TAU*t/2,slowPhase=TAU*t/spec.duration;
 const pts=[];
 let head,angle,scale;
 if(clip==='patrol'){
  const s=pathLength*t/8;
  for(let i=0;i<=N;i++){
   const u=i/N,p=along(s-(1-u)*385),pre=along(s-(1-u)*385-1),next=along(s-(1-u)*385+1);
   const dx=next.x-pre.x,dy=next.y-pre.y,len=Math.hypot(dx,dy);
   const w=15*Math.sin(TAU*2*u+phase)*Math.pow(Math.sin(Math.PI*u),2);
   pts.push({x:p.x-dy/len*w,y:p.y+dx/len*w,r:25*smooth(0,.22,u)*(1-.10*smooth(.7,1,u))});
  }
  head=pts[N];const p=along(s-1),q=along(s+1);angle=Math.atan2(q.y-p.y,q.x-p.x);scale=.29;
 }else{
  const anchor={x:490,y:304+3*Math.sin(phase)};
  for(let i=0;i<=N;i++){
   const u=i/N;
   pts.push({x:80+410*u,y:333-29*smooth(.66,1,u)+24*Math.sin(TAU*2*u+phase)*Math.pow(Math.sin(Math.PI*u),2)+3*Math.sin(phase)*u,r:26*smooth(0,.24,u)*(1-.14*smooth(.70,1,u))*(1+.01*Math.sin(slowPhase))});
  }
  let arc=0;for(let i=1;i<=N;i++)arc+=Math.hypot(pts[i].x-pts[i-1].x,pts[i].y-pts[i-1].y);
  // A fixed arc length prevents a stretchy accordion body as the wave propagates.
  const ratio=472/arc;
  for(const p of pts){p.x=anchor.x+(p.x-anchor.x)*ratio;p.y=anchor.y+(p.y-anchor.y)*ratio}
  head=pts[N];angle=.025*Math.sin(phase+.4)+.008*Math.cos(slowPhase);scale=.35;
 }
 return{pts,head,angle,scale,mirror:clip==='crawl-left',phase};
}
function outline(pts,offset=1){
 const side=(s)=>pts.map((p,i)=>{
  const a=pts[Math.max(0,i-1)],b=pts[Math.min(pts.length-1,i+1)],dx=b.x-a.x,dy=b.y-a.y,l=Math.hypot(dx,dy)||1;
  return{x:p.x-dy/l*p.r*s,y:p.y+dx/l*p.r*s};
 });
 const a=side(offset),b=side(-offset).reverse();
 return 'M'+[...a,...b].map(p=>f(p.x)+','+f(p.y)).join('L')+'Z';
}
export function svgAt(time,clip='crawl-right',reference='assets/mascot.png'){
 const {width,height}=CLIPS[clip],p=poseAt(time,clip);
 const connected=p.pts.map((q,i)=>{const u=i/(p.pts.length-1),v=smooth(.78,1,u);return{...q,x:q.x+v*(40*Math.cos(p.angle)+20*Math.sin(p.angle)),y:q.y+v*(40*Math.sin(p.angle)-20*Math.cos(p.angle))}});
 const body=outline(connected);
 const highlight=outline(connected.map(q=>({...q,y:q.y-q.r*.12,r:q.r*.50})));
 const mirror=p.mirror?'translate('+width+' 0) scale(-1 1)':'';
 // The crop is an animated source-image mask. No new face is drawn or regenerated.
 return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
 <defs>
 <linearGradient id="body" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#171717"/><stop offset=".52" stop-color="#1c1c1c"/><stop offset="1" stop-color="#171717"/></linearGradient>
 <clipPath id="head"><path d="M390 80H1060V350H690Q610 360 575 425H495Q450 400 390 350Z"/></clipPath>
 <clipPath id="body-clip"><path d="${body}"/></clipPath>
 </defs>
 <g transform="${mirror}">
 <path d="${body}" fill="url(#body)"/>
 <circle cx="${f(connected.at(-1).x)}" cy="${f(connected.at(-1).y)}" r="${f(connected.at(-1).r)}" fill="#1a1a1a"/>
 <path d="${highlight}" fill="#383838" opacity=".12" clip-path="url(#body-clip)"/>
 <g transform="translate(${f(p.head.x)} ${f(p.head.y)}) rotate(${f(p.angle*180/Math.PI)}) scale(${p.scale}) translate(-530 -405)">
 <image href="${reference}" width="1254" height="1254" clip-path="url(#head)"/>
 </g>
 </g></svg>`;
}


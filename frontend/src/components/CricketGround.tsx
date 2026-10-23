const fielders=[[300,135,'Keeper'],[344,143,'Slip'],[412,183,'Point'],[489,118,'Deep point'],[459,320,'Cover'],[363,385,'Long off'],[173,374,'Long on'],[114,267,'Midwicket'],[121,139,'Deep square'],[211,204,'Short leg'] ] as const;
export function CricketGround(){
 return <svg className="block h-auto w-full" viewBox="0 0 600 500" role="img" aria-label="Cricket oval with eleven fielding players, two batters, a pitch and an animated delivery">
 <defs><radialGradient id="out-turf"><stop offset="0" stopColor="#4b972d"/><stop offset="1" stopColor="#205b27"/></radialGradient><pattern id="out-mowing" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M0 0H40V40H0ZM40 40H80V80H40Z" fill="#b2e667" opacity=".055"/></pattern><filter id="out-dot-shadow"><feDropShadow dx="0" dy="3" stdDeviation="3" floodOpacity=".5"/></filter></defs>
 <ellipse cx="300" cy="255" rx="291" ry="232" fill="#132d1a"/><ellipse cx="300" cy="245" rx="281" ry="224" fill="url(#out-turf)" stroke="#a7d489" strokeWidth="3"/>
 {[0,1,2,3,4,5].map(i=><ellipse key={i} cx="300" cy="245" rx={268-i*33} ry={213-i*26} fill="none" stroke="#b8f075" strokeOpacity={i%2===0?'.10':'.03'} strokeWidth="17"/>)}
 <ellipse cx="300" cy="245" rx="277" ry="220" fill="url(#out-mowing)"/><ellipse cx="300" cy="245" rx="174" ry="141" fill="none" stroke="#e9f5d5" strokeOpacity=".65" strokeDasharray="8 9" strokeWidth="1.5"/>
 <path d="M300 25V465M23 245H577M100 90L500 400M500 90L100 400" stroke="#c9e7a8" strokeOpacity=".16"/>
 <rect x="278" y="163" width="44" height="146" rx="3" fill="#c9ae70"/><rect x="283" y="168" width="34" height="136" fill="#e0c583"/>
 <path d="M265 180H335M265 290H335M280 170V190M320 170V190M280 280V300M320 280V300" stroke="#fff7db" strokeWidth="2"/>
 {[174,292].map(y=><g key={y} stroke="#3b2d16" strokeWidth="2"><path d={`M296 ${y-8}v14M300 ${y-8}v14M304 ${y-8}v14M295 ${y-9}h10`}/></g>)}
 {fielders.map(([x,y,label],i)=><g key={label} transform={`translate(${x} ${y})`}><circle className="ground-fielder" style={{animationDelay:`${i*-.7}s`}} r="7" fill="#eef5ff" stroke="#406ca0" strokeWidth="3" filter="url(#out-dot-shadow)"/><title>{label}</title></g>)}
 <g className="ground-bowler"><circle r="8" fill="#eef5ff" stroke="#406ca0" strokeWidth="3" filter="url(#out-dot-shadow)"/><title>Bowler</title></g>
 <circle cx="311" cy="183" r="8" fill="var(--batter-fill)" stroke="var(--batter-outline)" strokeWidth="3"/><circle cx="288" cy="283" r="8" fill="var(--batter-fill)" stroke="var(--batter-outline)" strokeWidth="3"/>
 <path className="ground-shot" d="M300 182Q392 90 485 117" fill="none" stroke="#fff4bf" strokeWidth="2" strokeDasharray="5 7"/>
 <circle className="ground-ball" r="3.5" fill="var(--ball-fill)" stroke="#c14339" strokeWidth="1.5"/>
 </svg>;
}

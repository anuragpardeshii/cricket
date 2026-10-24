import { useId } from 'react';
export function Trophy({className='h-24 w-16',variant='cup'}:{className?:string;variant?:'cup'|'player'}){
  const id=useId().replace(/:/g,''); const gold=`url(#${id}-gold)`,dark=`url(#${id}-dark)`,orb=`url(#${id}-orb)`;
  return <svg role="img" aria-label={variant==='cup'?'Golden world championship trophy':'Player of the match trophy'} className={`gold-trophy ${className}`} viewBox="0 0 180 260">
    <defs>
      <linearGradient id={`${id}-gold`}><stop stopColor="#6c3903"/><stop offset=".18" stopColor="#e0a21c"/><stop offset=".36" stopColor="#fff3a7"/><stop offset=".5" stopColor="#d9980d"/><stop offset=".7" stopColor="#ffdc65"/><stop offset=".88" stopColor="#9b5806"/><stop offset="1" stopColor="#f4c53a"/></linearGradient>
      <linearGradient id={`${id}-dark`} x2="0" y2="1"><stop stopColor="#413724"/><stop offset=".35" stopColor="#101316"/><stop offset="1" stopColor="#030405"/></linearGradient>
      <radialGradient id={`${id}-orb`} cx="32%" cy="22%" r="80%"><stop stopColor="#fff2a0"/><stop offset=".25" stopColor="#f7cd48"/><stop offset=".55" stopColor="#ce8d05"/><stop offset=".82" stopColor="#8a4b02"/><stop offset="1" stopColor="#ffd556"/></radialGradient>
    </defs>
    <ellipse cx="90" cy="251" rx="67" ry="6" fill="#000" opacity=".2"/>
    <g className="trophy-float">
      <path d="M45 213Q90 202 135 213L153 239Q156 254 90 255Q24 254 27 239Z" fill={dark} stroke="#e1b749" strokeWidth="2"/>
      <ellipse cx="90" cy="214" rx="46" ry="12" fill={gold}/>
      {[43,65,90,115,137].map((x,i)=><ellipse key={x} cx={x} cy={235+(i===0||i===4?-3:2)} rx={i===0||i===4?7:10} ry="10" fill={gold} transform={`rotate(${(i-2)*12} ${x} 236)`}/>)}
      {variant==='cup'?<>
        <path d="M25 55C19 113 38 175 76 205M155 55C161 113 142 175 104 205" fill="none" stroke="#895106" strokeWidth="13"/>
        <path d="M25 55C19 113 38 175 76 205M155 55C161 113 142 175 104 205" fill="none" stroke={gold} strokeWidth="9"/>
        <path d="M90 99V205" stroke="#8b5709" strokeWidth="10"/><path d="M90 99V205" stroke={gold} strokeWidth="7"/>
        <path d="M76 203Q90 210 104 203L126 214Q90 227 54 214Z" fill={gold} stroke="#ffe291" strokeWidth=".6"/>
        <circle cx="90" cy="55" r="46" fill={orb} stroke="#edc75e"/>
        <g opacity=".22" fill="none" stroke="#714500" strokeWidth=".8"><ellipse cx="90" cy="55" rx="28" ry="45"/><ellipse cx="90" cy="55" rx="13" ry="45"/><ellipse cx="90" cy="55" rx="45" ry="23"/><path d="M47 39Q90 20 133 39M46 70Q90 91 134 70"/></g>
        <path d="m68 22 13-4 4 8 13-3 10 7-5 10-15 3-3 12-11 1-2-12-11-7Zm21 39 15-4 12 9-4 12-10 7-5-8-7-2Z" fill="#a56705" opacity=".28"/>
        <path d="M24 46Q90 33 156 46V60Q90 48 24 60Z" fill={gold} stroke="#fed764"/>
        <path d="M27 49Q90 39 153 49M27 57Q90 46 153 57" stroke="#fff3ae" opacity=".6" fill="none"/>
        <path className="trophy-glint" d="m61 22 3 9 9 3-9 3-3 9-3-9-9-3 9-3Z" fill="#fffbea"/>
      </>:<>
        <path d="M70 202h40l13 12H57Z" fill={gold}/>
        <path d="M84 132 66 177 70 201H82l-3-24 21-30 14 27-7 27h13l10-30-20-42Z" fill={gold} stroke="#ad760f"/>
        <path d="m81 78 24 7 9 48-33 10-9-35-22-14 6-12 24 12Z" fill={gold}/>
        <path d="m101 87 22 11 15-21 9 7-18 33-27-13Z" fill={gold}/>
        <circle cx="89" cy="61" r="16" fill={orb}/><path d="M72 59Q73 39 94 44L108 58Z" fill={gold}/>
        <g transform="rotate(32 135 77)"><rect x="130" y="31" width="10" height="58" rx="3" fill={gold} stroke="#b4780b"/><path d="M135 88v22" stroke={gold} strokeWidth="5"/></g>
        <circle cx="48" cy="53" r="8" fill={orb}/><path className="trophy-glint" d="m48 36 2 6 6 2-6 2-2 6-2-6-6-2 6-2Z" fill="#fff5bd"/>
      </>}
      <path d="M31 246Q90 260 149 246" fill="none" stroke="#fff0a2" strokeWidth="1.5" opacity=".7"/>
    </g>
  </svg>;
}

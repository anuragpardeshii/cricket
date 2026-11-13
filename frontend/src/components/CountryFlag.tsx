import { useState } from 'react';
const flags: Record<string, string> = { KENYA:'🇰🇪', BERMUDA:'🇧🇲', 'HONG KONG':'🇭🇰', ITALY:'🇮🇹', INDIA: '🇮🇳', AUSTRALIA: '🇦🇺', 'SRI LANKA': '🇱🇰', PAKISTAN: '🇵🇰', ENGLAND: '🏴\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}', 'SOUTH AFRICA': '🇿🇦', 'NEW ZEALAND': '🇳🇿', AFGHANISTAN: '🇦🇫', BANGLADESH: '🇧🇩', NETHERLANDS: '🇳🇱', CANADA:'🇨🇦', IRELAND:'🇮🇪', NAMIBIA:'🇳🇦', NEPAL:'🇳🇵', OMAN:'🇴🇲', 'PAPUA NEW GUINEA':'🇵🇬', SCOTLAND:'🏴\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}', UGANDA:'🇺🇬', 'UNITED STATES':'🇺🇸', 'UNITED ARAB EMIRATES':'🇦🇪', ZIMBABWE:'🇿🇼' };
const franchises = ['CHENNAI SUPER KINGS','DELHI CAPITALS','GUJARAT TITANS','KOLKATA KNIGHT RIDERS','LUCKNOW SUPER GIANTS','MUMBAI INDIANS','PUNJAB KINGS','RAJASTHAN ROYALS','ROYAL CHALLENGERS BENGALURU','SUNRISERS HYDERABAD'];
const historic = ['DECCAN CHARGERS','DELHI DAREDEVILS','KINGS XI PUNJAB','PUNE WARRIORS INDIA','KOCHI TUSKERS KERALA','RISING PUNE SUPERGIANT','GUJARAT LIONS'];
const aliases: Record<string,string> = { 'ROYAL CHALLENGERS BANGALORE':'ROYAL CHALLENGERS BENGALURU', 'PUNE WARRIORS':'PUNE WARRIORS INDIA', 'RISING PUNE SUPERGIANTS':'RISING PUNE SUPERGIANT' };
export function CountryFlag({ country }: { country: string }) {
  // Remount image state for each team so a failed logo never hides the next roll.
  const normalized = country.trim().replace(/\s+/g, ' ').toUpperCase();
  return <TeamMark key={normalized} country={country} club={aliases[normalized] ?? normalized}/>;
}
function TeamMark({country,club}:{country:string;club:string}) {
  const [failed,setFailed]=useState(false);
  const historical=historic.includes(club);
  const franchise=historical||franchises.includes(club);
  if(franchise&&!failed)return <img src={`/teams/${club.toLowerCase().replaceAll(' ','-')}.${historical?'png':'svg'}`} alt={`${country} franchise logo`} title={historical?'Historical franchise logo':'Current franchise logo'} onError={()=>setFailed(true)} className="inline-block size-10 object-contain align-middle"/>;
  if(franchise)return <span role="img" aria-label={`${country} franchise badge`} title={`${country} · logo unavailable`} className="inline-flex size-10 items-center justify-center rounded-full border border-amber/40 text-xs text-amber">{club.split(' ').map(s=>s[0]).join('')}</span>;
  // West Indies is a regional cricket team, not a single country's flag.
  return club === 'WEST INDIES' ? <span role="img" aria-label="West Indies cricket flag" className="inline-flex h-5 w-7 items-center justify-center rounded-sm bg-[#7b233a] align-middle text-[10px] text-white">☀</span> : <span role="img" aria-label={`${country} flag`}>{flags[club] ?? '🏏'}</span>;
}

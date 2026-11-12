import { useState } from 'react';
const flags: Record<string, string> = { KENYA:'🇰🇪', BERMUDA:'🇧🇲', 'HONG KONG':'🇭🇰', ITALY:'🇮🇹', INDIA: '🇮🇳', AUSTRALIA: '🇦🇺', 'SRI LANKA': '🇱🇰', PAKISTAN: '🇵🇰', ENGLAND: '🏴\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}', 'SOUTH AFRICA': '🇿🇦', 'NEW ZEALAND': '🇳🇿', AFGHANISTAN: '🇦🇫', BANGLADESH: '🇧🇩', NETHERLANDS: '🇳🇱', CANADA:'🇨🇦', IRELAND:'🇮🇪', NAMIBIA:'🇳🇦', NEPAL:'🇳🇵', OMAN:'🇴🇲', 'PAPUA NEW GUINEA':'🇵🇬', SCOTLAND:'🏴\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}', UGANDA:'🇺🇬', 'UNITED STATES':'🇺🇸', 'UNITED ARAB EMIRATES':'🇦🇪', ZIMBABWE:'🇿🇼' };
export function CountryFlag({ country }: { country: string }) {
  const [failed,setFailed]=useState(false);
  const franchises=['CHENNAI SUPER KINGS','DELHI CAPITALS','GUJARAT TITANS','KOLKATA KNIGHT RIDERS','LUCKNOW SUPER GIANTS','MUMBAI INDIANS','PUNJAB KINGS','RAJASTHAN ROYALS','ROYAL CHALLENGERS BENGALURU','SUNRISERS HYDERABAD'];
  const club=country.toUpperCase()==='ROYAL CHALLENGERS BANGALORE'?'ROYAL CHALLENGERS BENGALURU':country.toUpperCase();
  if(franchises.includes(club)&&!failed)return <img src={`/teams/${club.toLowerCase().replaceAll(' ','-')}.svg`} alt={`${country} franchise logo`} title="Current franchise logo" onError={()=>setFailed(true)} className="inline-block size-10 object-contain align-middle"/>;
  const historic=['DECCAN CHARGERS','DELHI DAREDEVILS','KINGS XI PUNJAB','PUNE WARRIORS INDIA','PUNE WARRIORS','KOCHI TUSKERS KERALA','RISING PUNE SUPERGIANTS','RISING PUNE SUPERGIANT','GUJARAT LIONS'];
  if(historic.includes(club))return <span title={`${country} · historical franchise`} className="inline-flex size-10 items-center justify-center rounded-full border border-amber/40 text-xs text-amber">{club.split(' ').map(s=>s[0]).join('')}</span>;
  // West Indies is a regional cricket team, not a single country's flag.
  return country.toUpperCase() === 'WEST INDIES' ? <span role="img" aria-label="West Indies cricket flag" className="inline-flex h-5 w-7 items-center justify-center rounded-sm bg-[#7b233a] align-middle text-[10px] text-white">☀</span> : <span role="img" aria-label={`${country} flag`}>{flags[country.toUpperCase()] ?? '🏏'}</span>;
}

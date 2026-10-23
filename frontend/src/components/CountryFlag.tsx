const flags: Record<string, string> = { INDIA: '🇮🇳', AUSTRALIA: '🇦🇺', 'SRI LANKA': '🇱🇰', PAKISTAN: '🇵🇰', ENGLAND: '🏴\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}', 'SOUTH AFRICA': '🇿🇦', 'NEW ZEALAND': '🇳🇿' };
export function CountryFlag({ country }: { country: string }) {
  // West Indies is a regional cricket team, not a single country's flag.
  return country.toUpperCase() === 'WEST INDIES' ? <span role="img" aria-label="West Indies cricket flag" className="inline-flex h-5 w-7 items-center justify-center rounded-sm bg-[#7b233a] align-middle text-[10px] text-white">☀</span> : <span role="img" aria-label={`${country} flag`}>{flags[country.toUpperCase()] ?? '🏏'}</span>;
}

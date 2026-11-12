import { useEffect, useState } from 'react';
type InstallEvent=Event&{prompt:()=>Promise<void>;userChoice:Promise<{outcome:string}>};
export function InstallApp(){
 const [prompt,setPrompt]=useState<InstallEvent|null>(null),[help,setHelp]=useState(false),[installed,setInstalled]=useState(()=>matchMedia('(display-mode: standalone)').matches||Boolean((navigator as Navigator&{standalone?:boolean}).standalone));
 useEffect(()=>{const ready=(e:Event)=>{e.preventDefault();setPrompt(e as InstallEvent)},done=()=>{setInstalled(true);setPrompt(null)};window.addEventListener('beforeinstallprompt',ready);window.addEventListener('appinstalled',done);return()=>{window.removeEventListener('beforeinstallprompt',ready);window.removeEventListener('appinstalled',done)}},[]);
 if(installed)return null;
 return <div className="mx-auto max-w-7xl px-4 py-3"><button className="text-xs text-amber" onClick={async()=>{if(prompt){await prompt.prompt();await prompt.userChoice;setPrompt(null)}else setHelp(!help)}}>＋ Add OUT. to your device</button>{help&&<p role="status" className="mt-2 max-w-xl text-xs leading-6 text-muted">On iPhone or iPad, open this site in Safari, tap Share, then Add to Home Screen. On Android or desktop, open your browser menu and choose Install app or Add to Home Screen if available. Online play requires an internet connection.</p>}</div>
}

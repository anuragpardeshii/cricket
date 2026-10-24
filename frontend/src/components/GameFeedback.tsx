import { useEffect, useRef, useState } from 'react';
let context: AudioContext | undefined;
const enabled=()=>{try{return localStorage.getItem('out-game-sound')!=='off'}catch{return true}};
function unlock(){
  if(!enabled())return;
  try { context??=new AudioContext(); if(context.state==='suspended')void context.resume().catch(()=>{}); } catch { /* Audio is optional on unsupported browsers. */ }
}
export function FeedbackToggle(){
  const [on,setOn]=useState(enabled);
  useEffect(()=>{
    window.addEventListener('pointerdown',unlock); window.addEventListener('keydown',unlock);
    return()=>{window.removeEventListener('pointerdown',unlock);window.removeEventListener('keydown',unlock)};
  },[]);
  return <button type="button" aria-label="Game sounds" aria-pressed={on} title={on?'Game sounds on':'Game sounds off'} onClick={()=>{const next=!on;setOn(next);try{localStorage.setItem('out-game-sound',next?'on':'off')}catch{/* Visit preference still works. */}if(next)unlock()}} className="inline-flex size-9 items-center justify-center rounded-full border border-neutral/15 text-muted hover:text-amber"><svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="m11 4-6 5H2v6h3l6 5V4Z"/>{on?<path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>:<path d="m16 9 6 6m0-6-6 6"/>}</svg></button>;
}
function once(key:string){try{if(sessionStorage.getItem(key))return false;sessionStorage.setItem(key,'1')}catch{/* Fall back to the mounted hook's guard. */}return true}
export function useTurnFeedback(active:boolean,key?:string){
  const last=useRef('');
  useEffect(()=>{if(!active||!key||last.current===key)return;last.current=key;if(once(`out-turn-${key}`)&&document.visibilityState==='visible'){try{navigator.vibrate?.([100,60,100])}catch{/* Haptics are optional. */}}},[active,key]);
}
export function useWinFeedback(key?:string){
  const last=useRef('');
  useEffect(()=>{
    if(!key||last.current===key)return;last.current=key;
    if(!once(`out-win-sound-${key}`)||!enabled()||!context||context.state!=='running')return;
    const start=context.currentTime;
    // A short original fanfare, generated locally without loading an audio file.
    [523.25,659.25,783.99,1046.5].forEach((frequency,i)=>{
      const oscillator=context!.createOscillator(),gain=context!.createGain();
      oscillator.type='triangle';oscillator.frequency.value=frequency;
      const at=start+i*.14;gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(.09,at+.025);gain.gain.exponentialRampToValueAtTime(.001,at+.5);
      oscillator.connect(gain);gain.connect(context!.destination);oscillator.start(at);oscillator.stop(at+.55);
      oscillator.onended=()=>{oscillator.disconnect();gain.disconnect()};
    });
  },[key]);
}

import { useEffect, useRef, useState } from 'react';
import { ConnectionState, DisconnectReason, Room as VoiceRoom, RoomEvent, Track, type Participant, type RemoteTrack, type RemoteParticipant } from 'livekit-client';
import { api, ApiError } from '../api';
import type { Room } from './types';

type VoiceConnection = { url: string; token: string };
type Peer = { id: string; muted: boolean; speaking: boolean };
type VoiceStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';
const button = 'inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-neutral/20 px-2 py-1 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber disabled:cursor-not-allowed disabled:opacity-40';

function Icon({ kind, off = false }: { kind: 'mic' | 'headphones'; off?: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4 shrink-0">
    {kind === 'mic' ? <><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/></> : <><path d="M3 14v-3a9 9 0 0 1 18 0v3"/><rect x="3" y="12" width="4" height="9" rx="2"/><rect x="17" y="12" width="4" height="9" rx="2"/></>}
    {off && <path d="m2 2 20 20"/>}
  </svg>;
}

function savedMutes(key: string): Set<string> {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(key) || '[]');
    return new Set(Array.isArray(value) ? value.filter((id): id is string => typeof id === 'string' && id.length === 36) : []);
  } catch { return new Set(); }
}

function memberId(participant: Participant): string {
  try { return JSON.parse(participant.metadata || '{}').memberId || participant.identity; }
  catch { return participant.identity; }
}

export default function RoomVoice({ room, available }: { room: Room; available: boolean }) {
  const storageKey = `out-voice-mutes:${room.id}:${room.you}`;
  const [status, setStatus] = useState<VoiceStatus>('disconnected');
  const [peers, setPeers] = useState<Peer[]>([]);
  const [micOn, setMicOn] = useState(false);
  const [micBusy, setMicBusy] = useState(false);
  const [deafened, setDeafened] = useState(false);
  const [muted, setMuted] = useState(() => savedMutes(storageKey));
  const [error, setError] = useState('');
  const [playbackBlocked, setPlaybackBlocked] = useState(false);
  const media = useRef<HTMLDivElement>(null);
  const voice = useRef<VoiceRoom | null>(null);
  const epoch = useRef(0);
  const preferences = useRef({ muted, deafened });
  preferences.current = { muted, deafened };
  const joined = status === 'connected' || status === 'reconnecting';

  const applyVolume = (participant: RemoteParticipant) => {
    const silent = preferences.current.deafened || preferences.current.muted.has(memberId(participant));
    participant.setVolume(silent ? 0 : 1, Track.Source.Microphone);
  };
  useEffect(() => {
    try { sessionStorage.setItem(storageKey, JSON.stringify([...muted])); } catch { /* Storage can be disabled. */ }
    voice.current?.remoteParticipants.forEach(applyVolume);
  }, [muted, deafened, storageKey]);
  useEffect(() => () => {
    epoch.current++;
    const current = voice.current;
    voice.current = null;
    current?.removeAllListeners();
    void current?.disconnect(true);
  }, []);

  const leave = () => {
    epoch.current++;
    const current = voice.current;
    voice.current = null;
    current?.removeAllListeners();
    void current?.disconnect(true);
    media.current?.replaceChildren();
    setPeers([]); setMicOn(false); setMicBusy(false); setDeafened(false);
    setPlaybackBlocked(false); setStatus('disconnected'); setError('');
  };

  const join = async () => {
    if (voice.current || status === 'connecting') return;
    const request = ++epoch.current;
    setStatus('connecting'); setError('');
    const current = new VoiceRoom({
      audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      publishDefaults: { stopMicTrackOnMute: true },
    });
    voice.current = current;
    const active = () => request === epoch.current && voice.current === current;
    const sync = () => {
      if (!active()) return;
      setPeers([current.localParticipant, ...current.remoteParticipants.values()].map(p => ({ id: memberId(p), muted: !p.isMicrophoneEnabled, speaking: p.isSpeaking })));
      setMicOn(current.localParticipant.isMicrophoneEnabled);
    };
    const attach = (track: RemoteTrack, _publication: unknown, participant: RemoteParticipant) => {
      if (!active() || track.kind !== Track.Kind.Audio) return;
      applyVolume(participant);
      const element = track.attach();
      element.dataset.voiceParticipant = memberId(participant);
      media.current?.appendChild(element);
      sync();
    };
    current.on(RoomEvent.TrackSubscribed, attach);
    current.on(RoomEvent.TrackUnsubscribed, track => { track.detach().forEach(element => element.remove()); sync(); });
    current.on(RoomEvent.ParticipantConnected, participant => { applyVolume(participant); sync(); });
    current.on(RoomEvent.ParticipantDisconnected, sync);
    current.on(RoomEvent.ActiveSpeakersChanged, sync);
    current.on(RoomEvent.TrackMuted, sync);
    current.on(RoomEvent.TrackUnmuted, sync);
    current.on(RoomEvent.LocalTrackPublished, sync);
    current.on(RoomEvent.LocalTrackUnpublished, sync);
    current.on(RoomEvent.AudioPlaybackStatusChanged, () => { if (active()) setPlaybackBlocked(!current.canPlaybackAudio); });
    current.on(RoomEvent.Reconnecting, () => { if (active()) setStatus('reconnecting'); });
    current.on(RoomEvent.Reconnected, () => {
      if (!active()) return;
      current.remoteParticipants.forEach(applyVolume); setStatus('connected'); sync();
    });
    current.on(RoomEvent.Disconnected, reason => {
      if (!active()) return;
      voice.current = null; epoch.current++;
      media.current?.replaceChildren();
      setStatus('disconnected'); setPeers([]); setMicOn(false); setMicBusy(false); setPlaybackBlocked(false);
      setError(reason === DisconnectReason.DUPLICATE_IDENTITY ? 'Voice chat was opened in another tab.' : reason === DisconnectReason.PARTICIPANT_REMOVED ? 'Your voice connection was ended.' : 'Voice disconnected. Join again when you are ready.');
    });
    // Unlock playback from this gesture. Joining never captures a microphone.
    void current.startAudio().catch(() => { if (active()) setPlaybackBlocked(true); });
    try {
      const connection = await api<VoiceConnection>(`/rooms/${room.id}/voice`, {});
      if (!active()) return;
      await current.connect(connection.url, connection.token, { autoSubscribe: true });
      if (!active()) { await current.disconnect(true); return; }
      setStatus('connected'); sync(); setPlaybackBlocked(!current.canPlaybackAudio);
    } catch (cause) {
      if (!active()) return;
      voice.current = null; epoch.current++;
      current.removeAllListeners(); await current.disconnect(true);
      media.current?.replaceChildren(); setStatus('disconnected'); setPeers([]);
      setError(cause instanceof ApiError ? cause.message : 'Could not connect to voice chat. Check your connection and try again.');
    }
  };

  const toggleMic = async () => {
    const current = voice.current;
    if (!current || current.state !== ConnectionState.Connected || micBusy) return;
    setMicBusy(true); setError('');
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('secure-context');
      await current.localParticipant.setMicrophoneEnabled(!current.localParticipant.isMicrophoneEnabled);
      if (voice.current !== current) { await current.disconnect(true); return; }
      setMicOn(current.localParticipant.isMicrophoneEnabled);
    } catch (cause) {
      if (voice.current !== current) return;
      const name = cause instanceof Error ? cause.name : '';
      setError(name === 'NotAllowedError' ? 'Microphone access was denied. Allow it in your browser settings, then try again.' : name === 'NotFoundError' ? 'No microphone was found. You can still listen.' : cause instanceof Error && cause.message === 'secure-context' ? 'Microphone access needs HTTPS or localhost. You can still listen.' : 'Could not start the microphone. Check your device and try again.');
    } finally { if (voice.current === current) setMicBusy(false); }
  };

  const toggleMute = (identity: string) => setMuted(previous => {
    const next = new Set(previous);
    if (next.has(identity)) next.delete(identity); else next.add(identity);
    return next;
  });
  const [expanded,setExpanded]=useState(false);
  const humans = room.state.members.filter(member => !member.is_ai && !member.departed);

  return <div className="relative" aria-label="Room voice chat">
    <p className="sr-only" role="status">{status === 'connecting' ? 'Joining voice…' : status === 'reconnecting' ? 'Reconnecting to voice…' : joined ? `${peers.length} in voice · ${micOn ? 'Your microphone is on' : 'Your microphone is off'}` : available ? 'Join with your microphone off.' : 'Voice chat is currently unavailable.'}</p>
    {joined?<button type="button" className={button} aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}><Icon kind="headphones"/>Voice · {peers.length} <span aria-hidden="true">⌄</span></button>:status==='connecting'?<button type="button" className={button} onClick={leave}>Cancel joining</button>:<button type="button" className={`${button} border-amber/40 bg-amber/10 text-amber`} disabled={!available} title="Join with your microphone off" onClick={()=>{setExpanded(true);void join()}}><Icon kind="headphones"/>Join voice</button>}
    {joined&&expanded&&<section aria-label="Voice controls" onKeyDown={e=>{if(e.key==='Escape')setExpanded(false)}} className="fixed right-3 top-32 z-40 mt-2 max-h-[70dvh] w-[min(420px,85vw)] overflow-y-auto rounded-xl border border-neutral/20 bg-panel p-3 shadow-xl sm:absolute sm:right-0 sm:top-full">
      <div className="flex flex-wrap items-center gap-2 border-b border-neutral/10 pb-3">
        <button type="button" className={`${button} ${micOn?'text-amber':''}`} disabled={micBusy||status!=='connected'} aria-pressed={micOn} onClick={()=>{void toggleMic()}}><Icon kind="mic" off={!micOn}/>{micBusy?'Please wait…':micOn?'Mute mic':'Unmute mic'}</button>
        <button type="button" className={button} aria-pressed={deafened} onClick={()=>setDeafened(v=>!v)}><Icon kind="headphones" off={deafened}/>{deafened?'Enable sound':'Turn off sound'}</button>
        <button type="button" className={`${button} text-danger`} onClick={leave}>Leave voice</button>
      </div>
      <ul className="grid gap-x-4 sm:grid-cols-2">{humans.map(member=>{
        const peer=peers.find(person=>person.id===member.id),personalMute=muted.has(member.id),yours=member.id===room.you;
        const speaking=peer?.speaking&&!peer.muted&&!personalMute&&!deafened;
        return <li key={member.id} className="flex min-w-0 items-center gap-2 border-b border-neutral/10 py-2">
          <span className={`flex size-7 shrink-0 items-center justify-center rounded-full border ${speaking?'border-success text-success':'border-neutral/15 text-muted'}`}><Icon kind="mic" off={!peer||peer.muted||personalMute}/></span>
          <div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold">{member.name}{yours?' (you)':''}</p><p className="text-[10px] text-muted">{personalMute?'Muted for you':!peer?'Not in voice':peer.muted?'Mic off':speaking?'Speaking':'Listening'}</p></div>
          {!yours&&<button type="button" className="shrink-0 rounded-md p-2 text-xs text-amber hover:bg-amber/10" aria-label={`${personalMute?'Unmute':'Mute'} ${member.name} for me`} aria-pressed={personalMute} onClick={()=>toggleMute(member.id)}>{personalMute?'Unmute':'Mute'}</button>}
        </li>;
      })}</ul>
      <p className="mt-2 text-[11px] text-muted">Muting a player affects only what you hear.</p>
      {playbackBlocked&&<button type="button" className={`${button} mt-2 text-amber`} onClick={()=>{void voice.current?.startAudio().catch(()=>setError('Your browser could not enable audio. Try again.'))}}>Enable voice playback</button>}
    </section>}
    {error&&<p role="alert" className="fixed right-3 top-32 z-50 mt-2 w-64 rounded-lg border border-danger/30 bg-panel p-3 text-xs text-danger sm:absolute sm:right-0 sm:top-full">{error}<button type="button" className="ml-2 text-amber" onClick={()=>setError('')}>Dismiss</button></p>}
    <div ref={media} hidden/>
  </div>;
}

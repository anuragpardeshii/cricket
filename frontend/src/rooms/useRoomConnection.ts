import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api';
import type { Room } from './types';

type Connection = { ticket: string; url: string; voiceAvailable: boolean };
export type LiveStatus = 'connecting' | 'live' | 'reconnecting';

export function useRoomConnection(roomId: string | undefined, onRoom: (room: Room) => void, onError: (error: unknown) => void) {
  const [status, setStatus] = useState<LiveStatus>('connecting');
  const [voiceAvailable, setVoiceAvailable] = useState(false);
  const callbacks = useRef({ onRoom, onError });
  callbacks.current = { onRoom, onError };
  useEffect(() => {
    setVoiceAvailable(false);
    setStatus('connecting');
    if (!roomId) return;
    let stopped = false;
    let socket: WebSocket | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let watchdog: ReturnType<typeof setInterval> | undefined;
    let attempts = 0;
    let lastMessage = 0;
    const schedule = () => {
      if (stopped) return;
      setStatus('reconnecting');
      const delay = Math.min(30000, 1000 * 2 ** Math.min(attempts++, 5)) + Math.random() * 500;
      retry = setTimeout(() => { void connect(); }, delay);
    };
    const connect = async () => {
      try {
        const connection = await api<Connection>(`/rooms/${roomId}/connection`, {});
        if (stopped) return;
        setVoiceAvailable(connection.voiceAvailable);
        const url = new URL(connection.url, window.location.href);
        url.protocol = url.protocol === 'http:' || url.protocol === 'ws:' ? 'ws:' : 'wss:';
        const current = new WebSocket(url);
        socket = current;
        lastMessage = Date.now();
        current.onopen = () => {
          if (stopped) { current.close(); return; }
          // Tickets travel in frames, never URLs or browser storage.
          current.send(JSON.stringify({ type: 'authenticate', ticket: connection.ticket }));
        };
        current.onmessage = event => {
          if (stopped) return;
          try {
            const message = JSON.parse(event.data);
            if (message.type !== 'room' && message.type !== 'heartbeat') return;
            lastMessage = Date.now(); attempts = 0; setStatus('live');
            if (message.type === 'room') callbacks.current.onRoom(message.room as Room);
          } catch { current.close(); }
        };
        watchdog = setInterval(() => {
          if (Date.now() - lastMessage > 25000) current.close();
          else if (current.readyState === WebSocket.OPEN) current.send(JSON.stringify({ type: 'ping' }));
        }, 10000);
        current.onclose = event => {
          clearInterval(watchdog);
          if (stopped) return;
          if (event.code === 4403) {
            stopped = true;
            callbacks.current.onError(new ApiError('You have left or been removed from this room.', 403));
          } else {
            // 4401 can mean the short-lived ticket expired in transit. Request a
            // fresh one; the HTTP endpoint will reject an actually expired session.
            schedule();
          }
        };
      } catch (error) {
        if (stopped) return;
        if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
          stopped = true; callbacks.current.onError(error);
        } else schedule();
      }
    };
    void connect();
    return () => {
      stopped = true; clearTimeout(retry); clearInterval(watchdog); socket?.close();
    };
  }, [roomId]);
  return { status, voiceAvailable };
}

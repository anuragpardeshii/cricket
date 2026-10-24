import { test, expect, type Page } from '@playwright/test';

type GameRoom = { id: string; code: string; you: string; state: { members: { id: string; name: string }[] } };

async function post<T>(page: Page, path: string, body: unknown): Promise<T> {
  return page.evaluate(async ({ path, body }) => {
    const session = await (await fetch('/api/auth/me')).json();
    const response = await fetch(`/api${path}`, { method: 'POST', headers: {
      'Content-Type': 'application/json', 'X-Out-Request': '1', 'X-CSRF-Token': session.csrf,
    }, body: JSON.stringify(body) });
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    return response.json();
  }, { path, body });
}

async function openRoom(page: Page, room: GameRoom) {
  await page.evaluate(id => sessionStorage.setItem('out-online-room', id), room.id);
  await page.reload();
  await expect(page.getByText('Live room connection', { exact: true })).toBeVisible();
}

async function audioVolume(page: Page, member: string) {
  return page.locator(`audio[data-voice-participant="${member}"]`).evaluate((audio: HTMLAudioElement) => audio.volume);
}

test('real voice, listener-only mute, reconnect, microphone denial, and kick removal', async ({ browser, baseURL }) => {
  const contexts = await Promise.all([0, 1, 2].map(() => browser.newContext({ baseURL, permissions: ['microphone'] })));
  const pages = await Promise.all(contexts.map(context => context.newPage()));
  const [a, b, c] = pages;
  const errors: string[] = [];
  try {
    for (const page of pages) {
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(() => {
        const state = window as unknown as { captures: number; peers: RTCPeerConnection[]; roomSockets: WebSocket[] };
        state.captures = 0; state.peers = []; state.roomSockets = [];
        const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
        navigator.mediaDevices.getUserMedia = (...args) => { state.captures++; return capture(...args); };
        const PeerConnection = window.RTCPeerConnection;
        window.RTCPeerConnection = class extends PeerConnection {
          constructor(...args: ConstructorParameters<typeof RTCPeerConnection>) { super(...args); state.peers.push(this); }
        };
        const Socket = window.WebSocket;
        window.WebSocket = class extends Socket {
          constructor(...args: ConstructorParameters<typeof WebSocket>) {
            super(...args);
            if (new URL(String(args[0])).pathname.endsWith('/live')) state.roomSockets.push(this);
          }
        };
      });
      await page.goto('/rooms');
      await expect.poll(async () => (await page.request.get('/api/auth/me')).status()).toBe(200);
    }
    const room = await post<GameRoom>(a, '/rooms', { format: 'knockout', capacity: 4, pick_seconds: 120, lobby_minutes: 30 });
    const bob = await post<GameRoom>(b, '/rooms/join', { code: room.code });
    const carol = await post<GameRoom>(c, '/rooms/join', { code: room.code });
    const aliceName = carol.state.members.find(m => m.id === room.you)!.name;
    const bobName = carol.state.members.find(m => m.id === bob.you)!.name;
    for (const page of pages) await openRoom(page, room);
    let roomGets = 0;
    b.on('request', request => { if (request.method() === 'GET' && request.url().endsWith(`/api/rooms/${room.id}`)) roomGets++; });
    for (const page of pages) {
      await page.getByRole('button', { name: 'Join voice', exact: true }).click();
      await expect(page.getByRole('button', { name: 'Unmute mic', exact: true })).toBeVisible();
      expect(await page.evaluate(() => (window as unknown as { captures: number }).captures)).toBe(0);
    }
    await expect(b.getByText('3 in voice · Your microphone is off', { exact: true })).toBeVisible();
    await b.setViewportSize({width:390,height:844});
    expect(await b.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    const voice=await b.getByRole('region',{name:'Voice controls',exact:true}).boundingBox();
    expect(voice!.x).toBeGreaterThanOrEqual(0);
    expect(voice!.x+voice!.width).toBeLessThanOrEqual(390);
    await b.screenshot({path:'test-results/compact-voice-mobile.png',fullPage:true});
    await b.setViewportSize({width:1280,height:720});
    await a.getByRole('button', { name: 'Unmute mic', exact: true }).click();
    await expect(a.getByRole('button', { name: 'Mute mic', exact: true })).toBeVisible();
    await expect.poll(() => audioVolume(b, room.you)).toBe(1);
    await expect.poll(() => audioVolume(c, room.you)).toBe(1);
    // Prove media packets arrived, in addition to checking controls and track attachment.
    await expect.poll(() => b.evaluate(async () => {
      let bytes = 0;
      for (const peer of (window as unknown as { peers: RTCPeerConnection[] }).peers) {
        (await peer.getStats()).forEach(stat => { if (stat.type === 'inbound-rtp' && stat.kind === 'audio') bytes += stat.bytesReceived || 0; });
      }
      return bytes;
    })).toBeGreaterThan(0);
    await b.getByRole('button', { name: `Mute ${aliceName} for me`, exact: true }).click();
    await expect.poll(() => audioVolume(b, room.you)).toBe(0);
    expect(await audioVolume(c, room.you)).toBe(1);
    await expect(a.getByRole('button', { name: 'Mute mic', exact: true })).toBeVisible();

    await c.getByRole('button', { name: 'Unmute mic', exact: true }).click();
    await expect.poll(() => audioVolume(b, carol.you)).toBe(1);
    await b.getByRole('button', { name: 'Turn off sound', exact: true }).click();
    await expect.poll(() => audioVolume(b, carol.you)).toBe(0);
    await b.getByRole('button', { name: 'Enable sound', exact: true }).click();
    await expect.poll(() => audioVolume(b, carol.you)).toBe(1);
    expect(await audioVolume(b, room.you)).toBe(0); // Deafen preserves personal mute.

    await a.getByRole('button', { name: 'Leave voice', exact: true }).click();
    await expect(a.getByText('3/4 players', { exact: true })).toBeVisible();
    await a.getByRole('button', { name: 'Join voice', exact: true }).click();
    await a.getByRole('button', { name: 'Unmute mic', exact: true }).click();
    await expect.poll(() => audioVolume(b, room.you)).toBe(0); // Mute survives republished tracks.
    await expect.poll(() => audioVolume(c, room.you)).toBe(1);

    await b.evaluate(() => (window as unknown as { roomSockets: WebSocket[] }).roomSockets.at(-1)!.close(4401));
    await expect(b.getByText('Reconnecting to room',{exact:true})).toBeVisible();
    await post(a, `/rooms/${room.id}/name`, { name: 'Live Alice' });
    await expect(b.getByText('Live room connection', { exact: true })).toBeVisible();
    await expect(b.getByRole('button', { name: 'Unmute Live Alice for me', exact: true })).toBeVisible();
    expect(roomGets).toBe(0); // Updates and recovery use sockets, without room polling.

    // A temporary restore failure must retain the room and retry automatically.
    await b.route(`**/api/rooms/${room.id}`, route => route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Temporary outage"}' }), { times: 1 });
    await b.reload();
    await expect(b.getByRole('button', { name: 'Join voice', exact: true })).toBeEnabled();
    await b.getByRole('button', { name: 'Join voice', exact: true }).click();
    await expect.poll(() => audioVolume(b, room.you)).toBe(0); // Mute survives refresh in this tab.
    await b.evaluate(() => {
      navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Denied for test', 'NotAllowedError'));
    });
    await b.getByRole('button', { name: 'Unmute mic', exact: true }).click();
    await expect(b.getByRole('alert')).toContainText('Microphone access was denied');
    await expect(b.getByRole('button', { name: 'Leave voice', exact: true })).toBeVisible();

    await b.setViewportSize({ width: 390, height: 844 });
    expect(await b.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await b.screenshot({ path: 'test-results/voice-mobile.png', fullPage: true });
    await a.screenshot({ path: 'test-results/voice-desktop.png', fullPage: true });

    // Suppress game socket handling: the media server must enforce removal itself.
    await b.evaluate(() => {
      const socket = (window as unknown as { roomSockets: WebSocket[] }).roomSockets.at(-1)!;
      socket.onmessage = null; socket.onclose = null; socket.close();
    });
    for(const page of [a,c]){const toggle=page.getByRole('button',{name:/^Voice ·/});if(await toggle.getAttribute('aria-expanded')==='true')await toggle.click()}
    await a.getByRole('button', { name: `Vote to kick ${bobName}`, exact: true }).click();
    await c.getByRole('button', { name: `Vote to kick ${bobName}`, exact: true }).click();
    await expect(b.getByRole('alert')).toContainText('Your voice connection was ended.');
    await expect(b.getByRole('button', { name: 'Join voice', exact: true })).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    await Promise.all(contexts.map(context => context.close()));
  }
});

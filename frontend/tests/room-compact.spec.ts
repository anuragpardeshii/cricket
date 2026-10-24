import { test, expect } from '@playwright/test';

test('eight seats fit one frame and IPL rolls stay in their competition',async({page})=>{
  await page.goto('/rooms');
  await expect.poll(async()=>(await page.request.get('/api/auth/me')).status()).toBe(200);
  await page.getByRole('button',{name:/Create a room/}).click();
  await expect(page.getByText('Time to join',{exact:true})).toHaveCount(0);
  await expect(page.getByText('Squad competition',{exact:true})).toBeVisible();
  const room=await page.evaluate(async()=>{
    const auth=await(await fetch('/api/auth/me')).json();
    const headers={'Content-Type':'application/json','X-Out-Request':'1','X-CSRF-Token':auth.csrf};
    const create=await fetch('/api/rooms',{method:'POST',headers,body:JSON.stringify({format:'knockout',competition:'ipl',capacity:8,pick_seconds:120})});
    if(!create.ok)throw new Error(await create.text());
    const room=await create.json();
    const ready=await(await fetch(`/api/rooms/${room.id}/ready`,{method:'POST',headers,body:JSON.stringify({ready:true})})).json();
    const started=await fetch(`/api/rooms/${room.id}/actions`,{method:'POST',headers,body:JSON.stringify({action:'start',version:ready.version})});
    if(!started.ok)throw new Error(await started.text());
    sessionStorage.setItem('out-online-room',room.id);
    return room;
  });
  await page.reload();
  await expect(page.getByRole('heading',{name:'Your turn',exact:true})).toBeVisible();
  await expect(page.getByRole('timer')).toContainText('to pick');
  await page.getByRole('button',{name:'ROLL SQUAD',exact:true}).click();
  const current=await(await page.request.get('/api/rooms/'+room.id)).json();
  expect(current.state.rolled.players.every((p:{competition:string})=>p.competition==='ipl')).toBe(true);
  const bar=page.getByRole('region',{name:'Teams in this game',exact:true});
  await expect(bar.getByRole('button',{name:/Preview .* team/})).toHaveCount(8);
  for(const width of [1280,390,320]){
    await page.setViewportSize({width,height:844});
    expect(await bar.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    expect((await bar.boundingBox())!.height).toBeLessThan(48);
    const chips=bar.locator('.team-chip');
    await expect(chips.first().locator('.team-full')).toBeVisible();
    await expect.poll(async()=> (await chips.first().boundingBox())!.width).toBeGreaterThan((await chips.nth(1).boundingBox())!.width);
    await page.screenshot({path:`test-results/eight-teams-${width}.png`,fullPage:true});
  }
  const seat=bar.getByRole('button',{name:'Preview AI 1 team',exact:true});
  const before=(await seat.boundingBox())!.width;
  await seat.focus();
  await expect.poll(async()=>(await seat.boundingBox())!.width).toBeGreaterThan(before);
  await seat.click();
  await expect(page.getByRole('heading',{name:'AI 1’s XI',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  // Leave this test room cleanly; AI completes the remaining picks.
  await page.getByRole('button',{name:'Exit match',exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:/Exit match|Leave|Confirm/}).click();
});

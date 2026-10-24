import { test, expect, type Page } from '@playwright/test';

type Room = {
  id:string; code:string; version:number; you:string; serverTime:number;
  state:{phase:string; turn:number; draftRevision:number; deadline:number; seconds:number; members:{id:string;name:string;ready:boolean;xi:Record<string,{id:string;name:string}>}[];
    rolled:{players:{id:string;name:string}[];allowedSlots:Record<string,string[]>}|null;
    matches:{timeline:{text?:string;over:string;innings:number}[]}[]};
};

async function post(page:Page,path:string,body:unknown):Promise<Room> {
  return page.evaluate(async({path,body})=>{
    const session=await(await fetch('/api/auth/me')).json();
    const response=await fetch('/api'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Out-Request':'1','X-CSRF-Token':session.csrf},body:JSON.stringify(body)});
    if(!response.ok)throw new Error(await response.text());
    return response.json();
  },{path,body});
}

test('ready gate, private rolls, live scorecards and win feedback',async({browser,baseURL})=>{
  test.setTimeout(210000);
  const contexts=await Promise.all([0,1].map(()=>browser.newContext({baseURL})));
  const [a,b]=await Promise.all(contexts.map(c=>c.newPage()));
  const errors:string[]=[];
  try{
    for(const page of [a,b]){
      page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(()=>{const w=window as unknown as {vibrations:number;sounds:number};w.vibrations=0;w.sounds=0;navigator.vibrate=()=>{w.vibrations++;return true};const original=AudioContext.prototype.createOscillator;AudioContext.prototype.createOscillator=function(){w.sounds++;return original.call(this)}});
      await page.goto('/rooms');
      await expect.poll(async()=>(await page.request.get('/api/auth/me')).status()).toBe(200);
    }
    let room=await post(a,'/rooms',{format:'knockout',capacity:2,pick_seconds:30,lobby_minutes:5});
    await post(b,'/rooms/join',{code:room.code});
    const path=`/rooms/${room.id}`;
    for(const page of [a,b]){
      await page.evaluate(id=>sessionStorage.setItem('out-online-room',id),room.id);
      await page.reload();
      await expect(page.getByText('Live room connection',{exact:true})).toBeVisible();
    }
    await expect(a.getByRole('button',{name:'Start match',exact:true})).toBeDisabled();
    await a.getByRole('button',{name:'Ready',exact:true}).click();
    await expect(b.getByText('1/2 players ready',{exact:true})).toBeVisible();
    await expect(a.getByRole('button',{name:'Start match',exact:true})).toBeDisabled();
    await b.getByRole('button',{name:'Ready',exact:true}).click();
    await expect(a.getByRole('button',{name:'Start match',exact:true})).toBeEnabled();
    await b.getByRole('button',{name:'Not ready',exact:true}).click();
    await expect(a.getByRole('button',{name:'Start match',exact:true})).toBeDisabled();
    await b.getByRole('button',{name:'Ready',exact:true}).click();
    await expect(a.getByText('2/2 players ready',{exact:true})).toBeVisible();
    await a.screenshot({path:'test-results/ready-lobby.png',fullPage:true});
    const started=a.waitForResponse(r=>r.url().endsWith(path+'/actions')&&r.request().method()==='POST');
    await a.getByRole('button',{name:'Start match',exact:true}).click();
    room=await(await started).json();
    const initialDeadline=room.state.deadline;
    await expect(a.getByRole('timer')).toHaveText(/2[0-8]s to pick/);
    const rolled=a.waitForResponse(r=>r.url().endsWith(path+'/actions')&&r.request().postDataJSON().action==='roll');
    await a.getByRole('button',{name:'ROLL SQUAD',exact:true}).click();
    room=await(await rolled).json();
    expect(room.state.deadline).toBeGreaterThan(initialDeadline);
    expect(room.state.deadline).toBe(room.serverTime+30);
    await expect(a.getByRole('button',{name:'Reroll · 3 left',exact:true})).toBeEnabled({timeout:1000});
    const player=room.state.rolled!.players.find(p=>room.state.rolled!.allowedSlots[p.id])!;
    const pickButton=a.locator('button[aria-pressed]').filter({has:a.getByText(player.name,{exact:true})});
    await pickButton.click();
    // Other players can rearrange their XI while the current player selects.
    room=await post(b,path+'/actions',{action:'formation',version:room.version,order:['b4','b3','b2','b1','wk','ar','n5','n4','n3','op2','op1']});
    await expect(pickButton).toHaveAttribute('aria-pressed','true');
    const picked=a.waitForResponse(r=>r.url().endsWith(path+'/actions')&&r.request().postDataJSON().action==='pick');
    await a.getByRole('button',{name:`Place ${player.name} at position`,exact:false}).first().click();
    room=await(await picked).json();
    await expect(b.getByRole('heading',{name:'Your turn',exact:true})).toBeVisible();
    expect(Object.values(room.state.members[0].xi).map(p=>p.id)).toContain(player.id);
    const nextRoll=b.waitForResponse(r=>r.url().endsWith(path+'/actions')&&r.request().postDataJSON().action==='roll');
    await b.getByRole('button',{name:'ROLL SQUAD',exact:true}).click();
    room=await(await nextRoll).json();
    const hidden=await (await a.request.get('/api'+path)).json();
    expect(hidden.state.rolled).toBeNull();
    await expect(a.getByRole('button',{name:/Reroll/})).toHaveCount(0);
    await expect(a.getByRole('button',{name:'My team',exact:true})).toHaveCount(0);
    await expect.poll(()=>b.evaluate(()=>(window as unknown as {vibrations:number}).vibrations)).toBe(1);
    const deadline=room.state.deadline;
    await expect(b.getByRole('timer')).toHaveText(/2[0-8]s to pick/);
    const reroll=b.waitForResponse(r=>r.url().endsWith(path+'/actions')&&r.request().postDataJSON().action==='roll');
    await b.getByRole('button',{name:'Reroll · 3 left',exact:true}).click();
    room=await(await reroll).json();
    expect(room.state.deadline).toBeGreaterThan(deadline);
    await b.setViewportSize({width:390,height:844});
    expect(await b.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await b.screenshot({path:'test-results/draft-mobile.png',fullPage:true});
    // Complete this test room through the real actions API, then watch its socket.
    while(room.state.phase==='draft'){
      const page=room.state.turn===0?a:b;
      if(!room.state.rolled)room=await post(page,path+'/actions',{action:'roll',version:room.version,draft_revision:room.state.draftRevision});
      const [id,slots]=Object.entries(room.state.rolled!.allowedSlots)[0];
      room=await post(page,path+'/actions',{action:'pick',version:room.version,draft_revision:room.state.draftRevision,player_id:id,slot_id:slots[0]});
    }
    await expect(a.getByRole('region',{name:'Match highlights',exact:true})).toBeVisible();
    await expect(a.getByRole('heading',{name:'The opening act',exact:true})).toBeVisible();
    await expect(a.getByLabel('Current score')).toContainText('OV 2');
    // A quiet over updates the score without adding a commentary card.
    await expect(a.getByRole('heading',{name:'The opening act',exact:true})).toBeVisible();
    await expect(a.getByText(/Earlier highlights/)).toHaveCount(0);
    await a.screenshot({path:'test-results/match-highlights-desktop.png',fullPage:true});
    await expect(b.getByRole('heading',{name:'Match highlights',exact:true})).toBeVisible();
    await b.screenshot({path:'test-results/match-highlights-mobile.png',fullPage:true});
    expect(await b.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await a.getByRole('button',{name:'Scorecards',exact:true}).click();
    await expect(a.getByRole('region',{name:'Match scorecard',exact:true})).toBeVisible();
    await expect(a.getByText('Live · updates each over',{exact:true})).toBeVisible();
    const score=await a.getByRole('region',{name:'Match scorecard',exact:true}).innerText();
    await expect.poll(()=>a.getByRole('region',{name:'Match scorecard',exact:true}).innerText()).not.toBe(score);
    await a.screenshot({path:'test-results/live-scorecard.png',fullPage:true});
    await a.getByRole('button',{name:'Bracket',exact:true}).click();
    await expect(a.getByRole('region',{name:'Match scorecard',exact:true})).toHaveCount(0);
    await expect.poll(async()=> (await(await a.request.get('/api'+path)).json()).state.phase,{timeout:140000,intervals:[2000]}).toBe('complete');
    const final=await (await a.request.get('/api'+path)).json();
    const winner=final.state.champion===final.you?a:b;
    await expect(winner.getByRole('dialog')).toBeVisible();
    await expect.poll(()=>winner.evaluate(()=>(window as unknown as {sounds:number}).sounds)).toBe(4);
    await winner.screenshot({path:'test-results/victory-trophy.png',fullPage:true});
    await winner.getByRole('button',{name:'Back to tournament',exact:true}).click();
    await winner.getByRole('button',{name:'Bracket',exact:true}).click();
    await expect(winner.getByRole('region',{name:'Match scorecard',exact:true})).toHaveCount(0);
    await winner.getByRole('button',{name:'Scorecards',exact:true}).click();
    await expect(winner.getByRole('region',{name:'Match scorecard',exact:true})).toBeVisible();
    expect(await winner.evaluate(()=>(window as unknown as {sounds:number}).sounds)).toBe(4);
    expect(errors).toEqual([]);
  }finally{
    await Promise.all(contexts.map(c=>c.close()));
  }
});

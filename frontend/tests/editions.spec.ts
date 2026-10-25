import { test, expect, type Page } from '@playwright/test';
import type { Squad } from '../src/game/types';

async function choose(page:Page,label:string,option:string) {
  await page.getByRole('combobox',{name:label,exact:true}).click();
  await page.getByRole('option',{name:option,exact:true}).click();
}

test('rooms use a competition-wide historical pool and explain the rules',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/rooms');
  await page.getByRole('button',{name:/Create a room/}).click();
  await choose(page,'Squad competition','ODI World Cup');
  await expect(page.getByRole('combobox',{name:'Squad edition',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:/Browse teams and players/})).toHaveCount(0);
  await expect(page.getByText(/Ready together/)).toHaveCount(0);
  await page.getByRole('button',{name:'How to play',exact:true}).click();
  const guide=page.getByRole('dialog',{name:'How to play'});
  await expect(guide).toContainText('any historical edition');
  await expect(guide).toContainText('ODI matches use 50 overs');
  await guide.getByRole('button',{name:'Got it'}).click();

  const created=page.waitForResponse(response=>response.url().endsWith('/api/rooms')&&response.request().method()==='POST');
  await page.getByRole('button',{name:/Create room/}).click();
  const room=await(await created).json();
  expect(room.state.competition).toBe('odi');
  expect(room.state.edition).toBeNull();
  await expect(page.getByText(/ODI World Cup/).first()).toBeVisible();
});

test('practice is T20 only and has no pool selectors or browser',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('combobox',{name:/Practice squad/})).toHaveCount(0);
  await expect(page.getByRole('button',{name:/Browse teams and players/})).toHaveCount(0);
  await expect(page.getByText(/Practice uses T20 rules/)).toBeVisible();
  const created=page.waitForResponse(response=>response.url().endsWith('/api/games')&&response.request().method()==='POST');
  await page.getByRole('button',{name:/Practice vs AI/}).click();
  const saved=await(await created).json();
  expect(saved.state.competition).toBe('t20');
  expect(saved.state.edition).toBeNull();
  const rolled=page.waitForResponse(response=>response.url().endsWith('/actions')&&response.request().postDataJSON().action==='roll');
  await page.getByRole('button',{name:'ROLL SQUAD',exact:true}).click();
  const state=(await(await rolled).json()).state;
  expect(state.rolled.tournament).toContain('T20 WORLD CUP');
  expect(state.rolled.players.every((player:{competition:string})=>player.competition==='t20')).toBe(true);
});

test('the archive API retains the earliest and latest historical editions',async({page})=>{
  await page.goto('/');
  await page.evaluate(async()=>{
    const response=await fetch('/api/auth/guest',{method:'POST',headers:{'Content-Type':'application/json','X-Out-Request':'1'},body:'{}'});
    if(!response.ok)throw new Error(await response.text());
  });
  for(const [competition,year,count,team] of [
    ['odi','1992',9,'ZIMBABWE'], ['odi','2023',10,'INDIA'],
    ['t20','2007',12,'KENYA'], ['t20','2026',20,'ITALY'],
    ['ipl','2008',8,'DECCAN CHARGERS'], ['ipl','2011',10,'KOCHI TUSKERS KERALA'],
    ['ipl','2026',10,'PUNJAB KINGS'],
  ] as const){
    const data=await (await page.request.get(`/api/catalog?competition=${competition}&edition=${year}`)).json();
    expect(data.squads).toHaveLength(count);
    expect(data.squads.some((squad:Squad)=>squad.country===team)).toBe(true);
  }
  const historic=await (await page.request.get('/api/catalog?competition=ipl&edition=2013')).json();
  const modern=await (await page.request.get('/api/catalog?competition=t20&edition=2024')).json();
  const player=(data:{squads:Squad[]},country:string,name:string)=>data.squads.find(s=>s.country===country)!.players.find(p=>p.name===name)!;
  expect(player(historic,'RAJASTHAN ROYALS','Harmeet Singh').personId).toBe(player(modern,'UNITED STATES','Harmeet Singh').personId);
});

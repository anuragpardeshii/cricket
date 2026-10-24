import { test, expect, type Page } from '@playwright/test';
import type { Squad } from '../src/game/types';

async function choose(page:Page,label:string,option:string) {
  await page.getByRole('combobox',{name:label,exact:true}).click();
  await page.getByRole('option',{name:option,exact:true}).click();
}

test('room edition selection, complete squad browser and live filtered roll',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  const errors:string[]=[]; page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/rooms');
  await page.getByRole('button',{name:/Create a room/}).click();
  await choose(page,'Squad competition','T20 World Cup');
  await expect(page.getByRole('combobox',{name:'Squad edition',exact:true})).toHaveText('2026 · 20 teams');
  await choose(page,'Squad edition','2024 · 20 teams');
  await page.getByRole('button',{name:/Browse teams and players/}).click();
  const squads=page.getByRole('combobox',{name:'View squad',exact:true});
  await expect(squads.locator('option')).toHaveCount(20);
  await squads.selectOption('UGANDA 2024');
  await expect(page.getByText('Brian Masaba',{exact:true})).toBeVisible();
  await choose(page,'Squad edition','2022 · 16 teams');
  await expect(squads.locator('option')).toHaveCount(16);
  await expect(squads.locator('option').filter({hasText:'UGANDA'})).toHaveCount(0);
  await choose(page,'Squad competition','IPL');
  await expect(squads.locator('option')).toHaveCount(10);
  await choose(page,'Squad edition','2023 · 10 teams');
  await expect(squads.locator('option').first()).toContainText('2023');
  await squads.selectOption('ROYAL CHALLENGERS BANGALORE 2023');
  await expect(page.getByText('V Kohli',{exact:true})).toBeVisible();
  await page.setViewportSize({width:320,height:740});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/historical-squads-mobile.png',fullPage:true});
  const created=page.waitForResponse(r=>r.url().endsWith('/api/rooms')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Create room',exact:false}).click();
  const room=await(await created).json();
  expect(room.state.competition).toBe('ipl'); expect(room.state.edition).toBe(2023);
  await expect(page.getByText('Live room connection',{exact:true})).toBeVisible();
  await expect(page.getByText(/^IPL 2023/).first()).toBeVisible();
  await page.getByRole('button',{name:'Ready',exact:true}).click();
  await page.getByRole('button',{name:'Start match',exact:true}).click();
  const rolled=page.waitForResponse(r=>r.url().endsWith('/actions')&&r.request().postDataJSON().action==='roll');
  await page.getByRole('button',{name:'ROLL SQUAD',exact:true}).click();
  const state=(await(await rolled).json()).state;
  expect(state.rolled.players.every((p:{competition:string;edition:number})=>p.competition==='ipl'&&p.edition===2023)).toBe(true);
  await page.reload();
  await expect(page.getByText(/^IPL 2023/).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('a new guest can browse and start practice with a historical edition',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await page.getByRole('combobox',{name:'Practice squad competition'}).selectOption('t20');
  await page.getByRole('combobox',{name:'Practice squad edition'}).selectOption('2022');
  await page.getByRole('button',{name:/Browse teams and players/}).click();
  const squads=page.getByRole('combobox',{name:'View squad',exact:true});
  await expect(squads.locator('option')).toHaveCount(16);
  await squads.selectOption('UNITED ARAB EMIRATES 2022');
  await expect(page.getByText('Muhammad Waseem',{exact:true})).toBeVisible();
  const created=page.waitForResponse(r=>r.url().endsWith('/api/games')&&r.request().method()==='POST');
  await page.getByRole('button',{name:/Practice vs AI/}).click();
  const game=await(await created).json();
  expect(game.state.competition).toBe('t20');expect(game.state.edition).toBe(2022);
  await expect(page.getByRole('heading',{name:'YOUR PICK',exact:true})).toBeVisible();
  const rolled=page.waitForResponse(r=>r.url().endsWith('/actions')&&r.request().postDataJSON().action==='roll');
  await page.getByRole('button',{name:'ROLL SQUAD',exact:true}).click();
  const state=(await(await rolled).json()).state;
  expect(state.rolled.tournament).toBe('T20 WORLD CUP 2022');
  expect(state.rolled.players.every((p:{edition:number})=>p.edition===2022)).toBe(true);
});


test('the full archive exposes the earliest and latest editions',async({page})=>{
  await page.goto('/');
  const competition=page.getByRole('combobox',{name:'Practice squad competition'});
  const edition=page.getByRole('combobox',{name:'Practice squad edition'});
  await page.getByRole('button',{name:/Browse teams and players/}).click();
  const squads=page.getByRole('combobox',{name:'View squad',exact:true});
  for(const [comp,year,count,team] of [
    ['odi','1992',9,'ZIMBABWE'], ['odi','2023',10,'INDIA'],
    ['t20','2007',12,'KENYA'], ['t20','2026',20,'ITALY'],
    ['ipl','2008',8,'DECCAN CHARGERS'], ['ipl','2011',10,'KOCHI TUSKERS KERALA'],
    ['ipl','2026',10,'PUNJAB KINGS'],
  ] as const){
    await competition.selectOption(comp);
    await edition.selectOption(year);
    await expect(squads.locator('option')).toHaveCount(count);
    await expect(squads.locator('option').filter({hasText:`${team} · ${year}`})).toHaveCount(1);
    await squads.selectOption(`${team} ${year}`);
    await expect(page.locator('#squad-library li')).not.toHaveCount(0);
  }
  await expect(edition.locator('option')).toHaveCount(20); // 19 seasons and All years
  await expect(edition.locator('option[value="2007"]')).toHaveCount(0);
  // The running API must also load the complete identity registry after migration.
  const historic=await (await page.request.get('/api/catalog?competition=ipl&edition=2013')).json();
  const modern=await (await page.request.get('/api/catalog?competition=t20&edition=2024')).json();
  const player=(data:{squads:Squad[]},country:string,name:string)=>data.squads.find(s=>s.country===country)!.players.find(p=>p.name===name)!;
  expect(player(historic,'RAJASTHAN ROYALS','Harmeet Singh').personId).toBe(player(modern,'UNITED STATES','Harmeet Singh').personId);
});

import { test,expect } from '@playwright/test';

for(const mobile of [false,true])test(`social lobby and draft ${mobile?'mobile':'desktop'}`,async({page})=>{
 await page.setViewportSize(mobile?{width:390,height:844}:{width:1280,height:900});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 const room:any={id:'test-room',code:'ABCD',version:1,serverTime:Date.now()/1000,you:'a',host:true,visibility:'private',standings:[],state:{phase:'lobby',format:'knockout',capacity:2,competition:'ipl',seconds:30,turn:0,taken:[],matches:[],champion:null,kickRequired:1,draftRevision:1,members:[{id:'a',name:'Alice',xi:{},is_ai:false,ready:false},{id:'b',name:'Bob',xi:{},is_ai:false,ready:true}]}};
 await page.addInitScript(()=>sessionStorage.setItem('out-online-room','test-room'));
 let broadcast=()=>{};
 await page.routeWebSocket('**/api/rooms/test-room/live',socket=>{broadcast=()=>socket.send(JSON.stringify({type:'room',room}));socket.onMessage(()=>broadcast())});
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;const body=route.request().method()==='POST'?route.request().postDataJSON():{};
  let result:any=room;
  if(path==='/api/auth/me')result={csrf:'test',user:{id:'a',username:'Alice'}};
  else if(path.endsWith('/connection'))result={ticket:'test',url:'/api/rooms/test-room/live',voiceAvailable:false};
  else if(path.endsWith('/ready')){room.state.members[0].ready=body.ready;room.version++}
  else if(path.endsWith('/settings')){room.state.seconds=body.pick_seconds;room.state.members.forEach((m:any)=>m.ready=false);room.version++}
  else if(path.endsWith('/chat')){room.state.chat=[{id:body.nonce,text:body.text,sender:'a',name:'Alice',sentAt:Date.now()/1000}];room.version++}
  else if(path.endsWith('/actions')){room.state.phase='draft';room.state.turn=1;room.state.deadline=Date.now()/1000+120;room.state.rolled={country:'MUMBAI INDIANS',tournament:'2013',players:[{id:'332-22',name:'Jasprit Bumrah',role:'PACE',rating:78,squad:'MUMBAI INDIANS 2013'}],allowedSlots:{'332-22':['b1']}};room.version++}
  await route.fulfill({json:result});broadcast();
 });
 await page.goto('/rooms');await expect(page.getByRole('heading',{name:'Waiting room'})).toBeVisible();
 await expect(page.getByRole('button',{name:/Preview.*team/})).toHaveCount(0);
 await page.getByRole('button',{name:'Ready',exact:true}).click();await expect(page.getByRole('button',{name:'Edit name',exact:true})).toBeDisabled();
 await page.getByRole('button',{name:'Match settings',exact:true}).click();await page.getByLabel('Pick timer (seconds)').fill('60');await page.getByRole('button',{name:'Save settings'}).click();
 await expect(page.getByText('0/2 players ready',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Edit name',exact:true})).toBeEnabled();
 await page.getByRole('button',{name:/Room chat/}).click();await page.getByRole('textbox',{name:'Chat message'}).fill('<script>alert(1)</script> Hello Bob');await page.getByRole('button',{name:'Send',exact:true}).click();
 await expect(page.getByRole('log')).toContainText('<script>alert(1)</script> Hello Bob');await expect(page.locator('aside script')).toHaveCount(0);
 room.host=false;room.version++;broadcast();
 await expect(page.getByRole('button',{name:'Match settings',exact:true})).toHaveCount(0);
 room.host=true;room.version++;broadcast();
 await expect(page.getByRole('button',{name:'Match settings',exact:true})).toBeVisible();
 await page.screenshot({path:`test-results/social-lobby-${mobile?'mobile':'desktop'}.png`,fullPage:true});
 room.state.members[1].ready=true;broadcast();await page.getByRole('button',{name:'Ready',exact:true}).click();await page.getByRole('button',{name:'Start match',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Bob is picking'})).toBeVisible();await expect(page.getByRole('img',{name:'MUMBAI INDIANS franchise logo'})).toBeVisible();
 await expect(page.getByRole('button',{name:/Jasprit Bumrah/})).toBeDisabled();await expect(page.getByRole('button',{name:/Reroll/})).toHaveCount(0);
 await expect(page.getByRole('log',{name:'Room messages'})).toBeVisible();
 if(!mobile){
  const chat=await page.getByRole('log',{name:'Room messages'}).boundingBox();
  const picking=await page.getByRole('heading',{name:'Bob is picking'}).boundingBox();
  expect(chat!.x).toBeGreaterThan(picking!.x+picking!.width);
  const panel=await page.getByRole('complementary',{name:'Room chat',exact:true}).boundingBox();
  expect(panel!.height).toBeGreaterThan(700);
  const composer=await page.getByRole('textbox',{name:'Chat message'}).boundingBox();
  expect(composer!.y).toBeGreaterThan(panel!.y+panel!.height-100);
 }
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:`test-results/draft-chat-${mobile?'mobile':'desktop'}.png`,fullPage:true});
 expect(errors).toEqual([]);
});

test('install manifest and icons are available',async({request})=>{
 const manifest=await(await request.get('/manifest.webmanifest')).json();expect(manifest.display).toBe('standalone');
 for(const icon of manifest.icons)expect((await request.get(icon.src)).status()).toBe(200);
 expect((await request.get('/sw.js')).status()).toBe(200);
});

test('completed review and same-room rematch',async({page})=>{
 const room:any={id:'test-room',code:'ABCD',version:1,serverTime:Date.now()/1000,you:'a',host:true,visibility:'private',standings:[],state:{phase:'complete',format:'knockout',capacity:2,competition:'ipl',seconds:30,turn:0,taken:[],champion:'b',kickRequired:1,members:[{id:'a',name:'Alice',xi:{},is_ai:false,ready:false},{id:'b',name:'Bob',xi:{},is_ai:false,ready:false}],matches:[{id:'m',a:'a',b:'b',status:'complete',winner:'b',round:1,scores:{youScore:'100/10',oppScore:'101/2'},result:{winner:'opp',margin:'by 8 wickets',analysis:{decisive:'Bob passed the target. Alice lost five wickets in the middle overs.',method:'Generated from the saved scorecard.',conditions:'Fantasy pitch assumptions are disclosed.',venue:{name:'Wankhede Stadium',city:'Mumbai',fact:'Home of Mumbai Indians.',source:'https://www.iplt20.com/venues',condition:'Batting surface'},teams:[{side:'you',name:'Alice',outcome:'Lost',notes:['Your top three scored 70 of 100 runs.'],players:[{name:'Jasprit Bumrah',squad:'MUMBAI INDIANS 2013',rating:78,note:'3 wickets in 2 IPL matches.',source:'https://www.mumbaiindians.com/news/from-2013-2024-the-jasprit-bumrah-road-to-greatness'}]},{side:'opp',name:'Bob',outcome:'Won',notes:['The attack took ten wickets.'],players:[]}]}}}]}};
 await page.addInitScript(()=>sessionStorage.setItem('out-online-room','test-room'));
 let broadcast=()=>{};await page.routeWebSocket('**/api/rooms/test-room/live',socket=>{broadcast=()=>socket.send(JSON.stringify({type:'room',room}));socket.onMessage(broadcast)});
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;let result:any=room;
  if(path==='/api/auth/me')result={csrf:'test',user:{id:'a',username:'Alice'}};
  else if(path.endsWith('/connection'))result={ticket:'test',url:'/api/rooms/test-room/live',voiceAvailable:false};
  else if(path.endsWith('/rematch')){room.version++;room.state.phase='lobby';room.state.matches=[];room.state.champion=null;room.state.roundNumber=2;result={code:'ABCD'}}
  await route.fulfill({json:result});broadcast();
 });
 await page.goto('/rooms');await expect(page.getByRole('heading',{name:'Where the match was decided'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Alice · Lost'})).toBeVisible();await expect(page.getByRole('heading',{name:'Bob · Won'})).toBeVisible();
 await page.getByText('Your XI: season evidence & ratings',{exact:true}).first().click();await expect(page.getByText('3 wickets in 2 IPL matches.',{exact:true})).toBeVisible();
 await page.screenshot({path:'test-results/match-review.png',fullPage:true});
 await page.getByRole('button',{name:'Play again',exact:true}).click();await expect(page.getByRole('heading',{name:'Waiting room'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'ABCD',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Start match',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>sessionStorage.getItem('out-online-room'))).toBe('test-room');
});


test('turn tone plays only on first chance, including the next snake round',async({page})=>{
 const room:any={id:'tone-room',code:'TONE',version:1,serverTime:Date.now()/1000,you:'a',host:true,visibility:'private',standings:[],state:{phase:'lobby',format:'knockout',capacity:2,competition:'ipl',seconds:30,turn:0,taken:[],matches:[],champion:null,kickRequired:1,draftRevision:1,draftRulesVersion:2,draftRound:1,turnPicks:0,members:[{id:'a',name:'Alice',xi:{},is_ai:false,ready:false},{id:'b',name:'Bob',xi:{},is_ai:false,ready:false}]}};
 await page.addInitScript(()=>{
  sessionStorage.setItem('out-online-room','tone-room');
  const w=window as any;w.tones=0;
  const original=AudioContext.prototype.createOscillator;
  AudioContext.prototype.createOscillator=function(){w.tones++;return original.call(this)};
 });
 let broadcast=()=>{};
 await page.routeWebSocket('**/api/rooms/tone-room/live',socket=>{broadcast=()=>{room.version++;socket.send(JSON.stringify({type:'room',room}))};socket.onMessage(broadcast)});
 await page.route('**/api/**',route=>{const path=new URL(route.request().url()).pathname;return route.fulfill({json:path==='/api/auth/me'?{csrf:'test',user:{id:'a',username:'Alice'}}:path.endsWith('/connection')?{ticket:'test',url:'/api/rooms/tone-room/live',voiceAvailable:false}:room})});
 await page.goto('/rooms');await expect(page.getByRole('heading',{name:'Waiting room'})).toBeVisible();
 await page.getByRole('button',{name:/Room chat/}).click(); // Unlock browser audio.
 room.state.phase='draft';room.state.deadline=Date.now()/1000+120;broadcast();
 await expect.poll(()=>page.evaluate(()=>(window as any).tones)).toBe(1);
 room.state.turnPicks=1;room.state.taken=['first'];broadcast();
 await expect(page.getByRole('status').filter({hasText:'Chance 2 of 2'})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).tones)).toBe(1);
 room.state.turn=1;room.state.turnPicks=0;broadcast();
 await expect(page.getByRole('heading',{name:'Bob is picking'})).toBeVisible();
 room.state.turn=0;room.state.draftRound=2;broadcast();
 await expect.poll(()=>page.evaluate(()=>(window as any).tones)).toBe(2);
 room.state.turnPicks=1;broadcast();
 await expect(page.getByRole('status').filter({hasText:'Chance 2 of 2'})).toBeVisible();
 room.state.turnPicks=0;room.state.draftRound=3;broadcast(); // Snake endpoint repeats the same player.
 await expect.poll(()=>page.evaluate(()=>(window as any).tones)).toBe(3);
 room.state.roundNumber=2;room.state.draftRound=1;broadcast();
 await expect.poll(()=>page.evaluate(()=>(window as any).tones)).toBe(4);
});

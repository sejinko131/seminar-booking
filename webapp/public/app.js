'use strict';
const $ = s => document.querySelector(s);
const days = ['월','화','수','목','금','토','일'];
const statuses = {pending:'승인 대기',approved:'예약 확정',rejected:'반려',cancelled:'취소'};
let statusData=null, currentBooking=null, role=null, activeView='reserve';
function el(tag, text='', cls='') {const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;}
function message(text=''){ $('#global-message').textContent=text; }
async function api(path,data){const res=await fetch(path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});const result=await res.json();if(!res.ok)throw Error(result.error||'요청에 실패했습니다.');return result;}
async function task(form, fn){const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);message();try{await fn();}catch(e){message(e.message);}finally{buttons.forEach(b=>b.disabled=false);}}
function values(form){return Object.fromEntries(new FormData(form));}
function kstDate(date=new Date()){return new Date(date.getTime()+9*3600000).toISOString().slice(0,10);}
const today=kstDate(), endDate=new Date(today+'T00:00:00+09:00');endDate.setUTCDate(endDate.getUTCDate()+21);
const general=$('#general-form'), regular=$('#regular-form');
general.elements.date.value=today;general.elements.date.min=today;general.elements.date.max=kstDate(endDate);
const month=today.slice(0,7), [y,m]=month.split('-').map(Number);
const monthEnd=new Date(Date.UTC(y,m,0)).toISOString().slice(0,10);
regular.elements.periodStart.value=today;regular.elements.periodEnd.value=monthEnd;
for(const name of ['periodStart','periodEnd']){regular.elements[name].min=month+'-01';regular.elements[name].max=monthEnd;}
function dayChoices(container,selected=[]){container.replaceChildren();for(const d of days){const label=el('label'),input=el('input');input.type='checkbox';input.name='weekdays';input.value=d;input.checked=selected.includes(d);label.append(input,document.createTextNode(d));container.append(label);}}
dayChoices($('#regular-days'));
function addPerson(){const i=$('#attendees').children.length;if(i>=30)return;const row=el('div','','person');for(const [name,title] of [['name','이름'],['studentId','학번']]){const label=el('label',(i===0?'대표자':'동반자 '+i)+' '+title);const input=el('input');input.dataset.field=name;input.required=true;input.maxLength=name==='name'?40:8;if(name==='studentId'){input.pattern='[0-9]{8}';input.inputMode='numeric';}label.append(input);row.append(label);}$('#attendees').append(row);}
addPerson();addPerson();
$('#add-person').onclick=addPerson;
$('#remove-person').onclick=()=>{if($('#attendees').children.length>2)$('#attendees').lastChild.remove();};
function receipt(target,result){target.hidden=false;target.replaceChildren(el('strong',statuses[result.status]),el('p','예약번호'),el('p',result.id,'receipt-number'),el('p','예약번호를 보관하세요. 입력한 관리 비밀번호와 함께 조회·수정·취소에 필요합니다.','hint'));target.focus();}
general.onsubmit=e=>{e.preventDefault();task(general,async()=>{const data=values(general);data.kind='general';data.periodStart=data.periodEnd=data.date;data.attendees=[...$('#attendees').children].map(row=>Object.fromEntries([...row.querySelectorAll('input')].map(n=>[n.dataset.field,n.value.trim()])));Object.assign(data,data.attendees[0]);const result=await api('/api/book',data);receipt($('#receipt'),result);general.elements.password.value='';await refreshStatus();});};
regular.onsubmit=e=>{e.preventDefault();task(regular,async()=>{const data=values(regular);data.kind='regular';data.weekdays=[...regular.querySelectorAll('[name=weekdays]:checked')].map(n=>n.value);const result=await api('/api/book',data);receipt($('#regular-receipt'),result);regular.elements.password.value='';await refreshStatus();});};
function showView(view){activeView=view;document.querySelectorAll('.view').forEach(n=>n.hidden=n.id!==view);document.querySelectorAll('[data-view]').forEach(n=>n.setAttribute('aria-pressed',String(n.dataset.view===view)));message();if(view==='calendar')refreshStatus().catch(e=>message(e.message));if(view==='admin'&&role==='admin')refreshAdmin().catch(e=>message(e.message));}
document.querySelectorAll('[data-view]').forEach(n=>n.onclick=()=>showView(n.dataset.view));
$('#admin-link').onclick=()=>showView('admin');
function inputField(form,name,label,type,value){const l=el('label',label),n=el('input');n.name=name;n.type=type;n.value=value;n.required=true;if(type==='time')n.step=600;l.append(n);form.append(l);return n;}
function renderBooking(b){currentBooking=b;const target=$('#manage-result');target.replaceChildren();$('#manage-login').hidden=true;const card=el('div','','booking-card');card.append(el('strong',statuses[b.status]),el('p',b.period_start+' ~ '+b.period_end+' · '+b.start_time+' ~ '+b.end_time),el('p',b.attendees.map(p=>p.name+'('+p.studentId+')').join(', '),'hint'));
if(b.kind==='regular')card.append(el('p',b.group_name+' · '+b.weekdays.join(', ')),el('p',b.purpose,'hint'));
target.append(card);if(!['approved','pending'].includes(b.status))return;
const form=el('form');inputField(form,'periodStart','사용 시작일','date',b.period_start);
if(b.kind==='regular')inputField(form,'periodEnd','사용 종료일','date',b.period_end);
inputField(form,'startTime','시작시간','time',b.start_time);inputField(form,'endTime','종료시간','time',b.end_time);
if(b.kind==='regular'){const fieldset=el('fieldset');fieldset.append(el('legend','요일'));const choices=el('div','','day-options');dayChoices(choices,b.weekdays);fieldset.append(choices);form.append(fieldset);}
const save=el('button','변경 저장','primary full');save.type='submit';form.append(save);card.append(form);
form.onsubmit=e=>{e.preventDefault();task(form,async()=>{const data=values(form);Object.assign(data,{action:'edit',version:b.version,name:b.name,studentId:b.student_id,attendees:b.attendees,groupName:b.group_name,contact:b.contact,purpose:b.purpose});if(b.kind==='general')data.periodEnd=data.periodStart;else data.weekdays=[...form.querySelectorAll('[name=weekdays]:checked')].map(n=>n.value);renderBooking((await api('/api/edit',data)).booking);message('변경되었습니다.'+(b.kind==='regular'?' 관리자 승인 후 확정됩니다.':''));await refreshStatus();});};
const cancel=el('button','예약 취소','cancel full');cancel.type='button';card.append(cancel);cancel.onclick=()=>{if(!confirm('이 예약을 취소할까요?'))return;task(card,async()=>{renderBooking((await api('/api/edit',{action:'cancel',version:b.version})).booking);await refreshStatus();message('예약이 취소되었습니다.');});};}
$('#manage-login').onsubmit=e=>{e.preventDefault();task(e.target,async()=>{const r=await api('/api/login',values(e.target));role=r.role;renderBooking(r.booking);e.target.reset();});};
$('#admin-login').onsubmit=e=>{e.preventDefault();task(e.target,async()=>{await api('/api/login',{...values(e.target),role:'admin'});role='admin';$('#manage-result').replaceChildren();$('#manage-login').hidden=false;e.target.reset();e.target.hidden=true;$('#admin-dashboard').hidden=false;await refreshAdmin();});};
document.querySelectorAll('.logout').forEach(n=>n.onclick=()=>task(n.parentElement,async()=>{await api('/api/logout',{});role=null;currentBooking=null;$('#manage-login').hidden=false;$('#manage-result').replaceChildren();$('#admin-login').hidden=false;$('#admin-dashboard').hidden=true;$('#admin-rows').replaceChildren();message('로그아웃되었습니다.');}));
async function refreshAdmin(){const r=await api('/api/admin');const target=$('#admin-rows');target.replaceChildren();for(const b of r.bookings){const card=el('div','','booking-card');card.append(el('strong',(b.kind==='regular'?b.group_name:'일반예약')+' · '+statuses[b.status]),el('p',b.name+' / '+b.student_id+(b.contact?' / '+b.contact:'')),el('p',b.period_start+' ~ '+b.period_end+' / '+b.weekdays.join(', ')+' / '+b.start_time+' ~ '+b.end_time),el('p',b.purpose,'hint'),el('p',b.attendees.map(p=>p.name+'('+p.studentId+')').join(', '),'hint'));
const actions=[];if(b.kind==='regular'&&b.status==='pending')actions.push(['approve','승인'],['reject','반려']);if(['approved','pending'].includes(b.status))actions.push(['cancel','취소']);
for(const [action,label] of actions){const button=el('button',label,action==='cancel'?'cancel':'secondary');button.type='button';button.onclick=()=>{if(!confirm(label+' 처리할까요?'))return;task(card,async()=>{await api('/api/admin/action',{id:b.id,version:b.version,action});await refreshAdmin();await refreshStatus();});};card.append(button);}target.append(card);}
if(!r.bookings.length)target.append(el('p','등록된 신청이 없습니다.','hint'));}
$('#admin-refresh').onclick=()=>refreshAdmin().catch(e=>message(e.message));
$('#booking-toggle').onclick=()=>task($('#admin-dashboard'),async()=>{await refreshStatus();const enabled=!statusData.enabled;if(!confirm('신규 예약 접수를 '+(enabled?'시작':'중지')+'할까요?'))return;await api('/api/admin/settings',{enabled});await refreshStatus();});
function weekOptions(){const [year,mon]=$('#calendar-month').value.split('-').map(Number);if(!year||!mon)return;const first=new Date(Date.UTC(year,mon-1,1)),last=new Date(Date.UTC(year,mon,0));first.setUTCDate(first.getUTCDate()-(first.getUTCDay()+6)%7);const select=$('#calendar-week');select.replaceChildren();let i=1;while(first<=last){const option=el('option',i+'주차 · '+first.toISOString().slice(5,10));option.value=first.toISOString().slice(0,10);select.append(option);first.setUTCDate(first.getUTCDate()+7);i++;}const t=new Date(today+'T00:00:00Z');t.setUTCDate(t.getUTCDate()-(t.getUTCDay()+6)%7);if([...select.options].some(o=>o.value===t.toISOString().slice(0,10)))select.value=t.toISOString().slice(0,10);}
$('#calendar-month').value=month;weekOptions();
$('#calendar-month').onchange=()=>{weekOptions();renderCalendar();};
$('#calendar-week').onchange=renderCalendar;
function kstTimestamp(date,hour=0){return Date.parse(date+'T00:00:00+09:00')+hour*3600000;}
function renderCalendar(){if(!statusData)return;const start=$('#calendar-week').value;if(!start)return;const table=el('table','','schedule'),head=el('thead'),hr=el('tr');hr.append(el('th','시간'));const dates=[];for(let i=0;i<7;i++){const d=new Date(start+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+i);const s=d.toISOString().slice(0,10);dates.push(s);hr.append(el('th',days[i]+' '+s.slice(5)));}head.append(hr);table.append(head);const body=el('tbody');for(let h=0;h<24;h++){const row=el('tr');row.append(el('th',String(h).padStart(2,'0')+':00'));for(const d of dates){const cell=el('td');for(const event of statusData.events){if(Date.parse(event.starts)<kstTimestamp(d,h+1)&&Date.parse(event.ends)>kstTimestamp(d,h))cell.append(el('div',event.label+' '+event.starts.slice(11,16)+'~'+event.ends.slice(11,16),'event '+event.kind));}row.append(cell);}body.append(row);}table.append(body);$('#schedule').replaceChildren(table);$('#calendar-updated').textContent='한국시간 기준 · 마지막 갱신 '+statusData.updatedAt.slice(0,19).replace('T',' ')+' · 60초마다 갱신';const upcoming=$('#upcoming');upcoming.replaceChildren();for(const event of statusData.events.slice(0,30))upcoming.append(el('p',event.starts.slice(0,10)+' '+event.starts.slice(11,16)+' ~ '+event.ends.slice(0,16).replace('T',' ')+' · '+event.label,'hint'));if(!statusData.events.length)upcoming.append(el('p','예정된 확정 예약이 없습니다.','hint'));}
async function refreshStatus(){statusData=await api('/api/status');$('#booking-toggle').textContent='신규 예약 접수: '+(statusData.enabled?'ON':'OFF')+' · 변경';renderCalendar();}
setInterval(()=>{if(activeView==='calendar'||role==='admin')refreshStatus().catch(e=>message('현황 조회 실패: '+e.message));},60000);
refreshStatus().catch(e=>message('현황 조회 실패: '+e.message));
api('/api/me').then(r=>{role=r.role;if(role==='booking')renderBooking(r.booking);else{$('#admin-login').hidden=true;$('#admin-dashboard').hidden=false;}}).catch(()=>{});

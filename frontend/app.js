

const API = location.origin + '/api';
let TOKEN = localStorage.getItem('token') || '';
let CURRENT_TEST = { kind: '', session_id: 0 };

function $(id){ return document.getElementById(id); }
function show(id){ const e=$(id); if(e) e.classList.remove('hidden'); }
function hide(id){ const e=$(id); if(e) e.classList.add('hidden'); }
function msg(id, text){ const e=$(id); if(e) e.textContent = text; }

function authHeaders(){ 
  return { 
    'Content-Type':'application/json', 
    'Authorization': 'Bearer ' + TOKEN 
  }; 
}

/* ----------------- Auth ----------------- */
async function signup(){
  try{
    const email = $('signupEmail').value.trim();
    const password = $('signupPassword').value;
    const r = await fetch(API + '/signup', { 
      method:'POST', 
      headers:{'Content-Type':'application/json'}, 
      body: JSON.stringify({email,password})
    });
    const data = await r.json();
    msg('authMsg', data.error || 'Account created. Please login.');
  }catch(err){
    console.error('Signup error', err);
    msg('authMsg', 'Signup failed. Try again.');
  }
}

async function login(){
  try{
    const email = $('loginEmail').value.trim();
    const password = $('loginPassword').value;
    const r = await fetch(API + '/login', { 
      method:'POST', 
      headers:{'Content-Type':'application/json'}, 
      body: JSON.stringify({email,password})
    });
    const data = await r.json();
    if(data.token){
      TOKEN = data.token; 
      localStorage.setItem('token', TOKEN); // save token
      msg('authMsg', 'Login successful');
      hide('auth'); 
      show('formSection');
    } else { 
      msg('authMsg', data.error || 'Login failed'); 
    }
  }catch(err){
    console.error('Login error', err);
    msg('authMsg', 'Login error. Try again.');
  }
}

/* ----------------- Form & Flow ----------------- */
async function saveForm(){
  try{
    const payload = {
      highest_qualification: $('hq').value,
      stream: $('stream').value,
      board_marks: Number($('marks').value||0),
      city: $('city').value,
      country: $('country').value,
      abroad: $('abroad').value === 'true',
      budget: Number($('budget').value||0),
      dream_course: $('dream').value || null
    };
    const r = await fetch(API + '/form', { 
      method:'POST', 
      headers: authHeaders(), 
      body: JSON.stringify(payload) 
    });
    const data = await r.json();
    if(data.error){
      msg('formMsg', data.error);
      return;
    }
    msg('formMsg', 'Saved. Processing...');

    // New flow rules:
    // 1) If Class 10 => skip tests and show recommendations directly
    // 2) Else if dream_course provided => run aptitude test
    // 3) Else => run personality test
    const hq = (payload.highest_qualification||'').toString().trim().toLowerCase();
    if(hq === 'class 10' || hq === '10' || hq === 'class10'){
      // directly get recommendations
      await getRecommendations();
      return;
    }

    if(payload.dream_course){
      // run aptitude test
      await startTest('aptitude');
      return;
    } else {
      // run personality test
      await startTest('personality');
      return;
    }
  }catch(err){
    console.error('saveForm error', err);
    msg('formMsg', 'Error saving form. Try again.');
  }
}

/* ----------------- Tests ----------------- */
async function startAptitude(){ await startTest('aptitude'); }
async function startPersonality(){ await startTest('personality'); }

async function startTest(kind){
  try{
    hide('resultsCard');
    const r = await fetch(API + '/test/start', { 
      method:'POST', 
      headers: authHeaders(), 
      body: JSON.stringify({kind})
    });
    const data = await r.json();
    if(data.session_id){
      CURRENT_TEST = { kind, session_id: data.session_id };
      $('testTitle').textContent = kind === 'aptitude' ? 'Aptitude Test (max 20)' : 'Personality Test (max 20)';
      const box = $('questions'); if(!box) return;
      box.innerHTML = '';
      data.questions.forEach(q => {
        const div = document.createElement('div');
        div.className = 'q';
        div.innerHTML = `<p><b>Q${q.id}.</b> ${q.question}</p>`;
        const opts = document.createElement('div');
        for(const [k,v] of Object.entries(q.options)){
          opts.innerHTML += `<label class="opt"><input type="radio" name="q_${q.id}" value="${k}"> ${k}) ${v}</label>`;
        }
        div.appendChild(opts); box.appendChild(div);
      });
      show('testCard');
      msg('testMsg','');
    } else {
      msg('formMsg', data.error || 'Unable to start test');
    }
  }catch(err){
    console.error('startTest error', err);
    msg('formMsg', 'Cannot start test. Try again.');
  }
}

async function submitTest(){
  try{
    const answers = {};
    Array.from(document.querySelectorAll('.q')).forEach(div => {
      const input = div.querySelector('input[type=radio]');
      if(!input) return;
      const name = input.name;
      const qid = Number(name.split('_')[1]);
      const chosen = (div.querySelector(`input[name=${name}]:checked`)||{}).value;
      if(chosen) answers[qid] = chosen;
    });
    const r = await fetch(API + '/test/submit', { 
      method:'POST', 
      headers: authHeaders(), 
      body: JSON.stringify({ session_id: CURRENT_TEST.session_id, answers })
    });
    const data = await r.json();
    if(CURRENT_TEST.kind === 'aptitude'){
      msg('testMsg', `Score: ${data.score} / ${data.out_of}`);
    } else {
      msg('testMsg', `Personality: ${Object.entries(data.traits||{}).map(([k,v])=>`${k}:${v}`).join(', ')}`);
    }
    hide('testCard');

    // After submitting test, automatically fetch recommendations
    await getRecommendations();
  }catch(err){
    console.error('submitTest error', err);
    msg('testMsg', 'Error submitting test. Try again.');
  }
}

/* ----------------- Recommendations, Resources, Colleges ----------------- */
async function getRecommendations(){
  try{
    const r = await fetch(API + '/recommendations', { 
      method:'POST', 
      headers: authHeaders(), 
      body: JSON.stringify({}) 
    });
    const data = await r.json();
    if(!data.courses){ msg('formMsg', data.error || 'Error getting recommendations.'); return; }
    show('resultsCard');
    const list = $('recCourses'); 
    list.innerHTML = `<p><b>Personality:</b> ${data.personality} | <b>Aptitude(0-20):</b> ${data.aptitude20}</p>`;
    const tbl = document.createElement('table');
    tbl.innerHTML = `<tr><th>Course</th><th>Fit</th></tr>`;
    const pick = $('coursePick'); if(pick) pick.innerHTML = '';
    data.courses.forEach(c => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${c.name} (${c.code})</td><td>${c.fit}</td>`;
      tbl.appendChild(tr);
      if(pick){
        const opt = document.createElement('option'); 
        opt.value = c.code; 
        opt.textContent = `${c.name} (${c.code})`;
        pick.appendChild(opt);
      }
    });
    list.appendChild(tbl);
  }catch(err){
    console.error('getRecommendations error', err);
    msg('formMsg', 'Failed to get recommendations.');
  }
}

async function loadResources(){
  try{
    const code = $('coursePick').value;
    const r = await fetch(API + '/resources', { 
      method:'POST', 
      headers: authHeaders(), 
      body: JSON.stringify({ course_code: code })
    });
    const data = await r.json();
    const box = $('resources'); if(!box) return;
    box.innerHTML = '<h3>Free Resources</h3>';
    const ul = document.createElement('ul');
    (data.resources||[]).forEach(rr => { 
      ul.innerHTML += `<li><a href="${rr.url}" target="_blank">${rr.title}</a></li>`; 
    });
    box.appendChild(ul);
  }catch(err){
    console.error('loadResources error', err);
    msg('formMsg', 'Failed to load resources.');
  }
}

async function loadColleges(){
  try{
    const code = $('coursePick').value;
    const payload = {
      course_code: code,
      city: $('city').value,
      country: $('country').value,
      abroad: $('abroad').value === 'true',
      budget: Number($('budget').value||0),
      include_private: true,
      include_government: true
    };
    const r = await fetch(API + '/colleges', { 
      method:'POST', 
      headers: authHeaders(), 
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    const box = $('colleges'); if(!box) return;
    box.innerHTML = '<h3>Matching Colleges</h3>';
    const tbl = document.createElement('table');
    tbl.innerHTML = `<tr><th>Name</th><th>City</th><th>Country</th><th>Type</th><th>Fees/Year</th><th>Scholarships</th><th>Placements</th></tr>`;
    (data.colleges||[]).forEach(c => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td><a href="${c.website}" target="_blank">${c.name}</a></td><td>${c.city}</td><td>${c.country}</td><td>${c.is_government? 'Govt' : 'Private'}</td><td>${c.fees_per_year}</td><td>${c.scholarships||''}</td><td>${c.placements||''}</td>`;
      tbl.appendChild(tr);
    });
    box.appendChild(tbl);
  }catch(err){
    console.error('loadColleges error', err);
    msg('formMsg', 'Failed to load colleges.');
  }
}

/* ----------------- Utilities ----------------- */
function logout(){
  localStorage.removeItem('token');
  TOKEN = '';
  show('auth');
  hide('formSection');
  hide('resultsCard');
  msg('authMsg', 'Logged out successfully');
}

// On load: restore token and show form if present
(function initOnLoad(){
  const savedToken = localStorage.getItem('token');
  if(savedToken){
    TOKEN = savedToken; 
    hide('auth'); 
    show('formSection');
  }
})();

'use strict';
const dataBase = location.hostname.endsWith('.github.io')
  ? 'https://raw.githubusercontent.com/MattHCoding/Madison-Fantasy-League-Pro-Bowl-Scoreboard/main/' : './';
let config, snapshot;
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(path) {
  const response = await fetch(dataBase + path, {cache:'no-store'});
  if (!response.ok) throw new Error('Could not load annual setup.');
  return response.json();
}
function populatePlayers() {
  for (const side of ['west','east']) {
    config.sides[side].players.forEach((selection, index) => {
      const select = document.getElementById(`${side}-${index}`);
      const previous = select.value || selection.id;
      const allowed = selection.slot === 'FLEX' ? ['RB','WR','TE'] : [selection.slot];
      const owners = new Set(config.sides[side].teamIds.map(String));
      const players = snapshot.teams.filter(t => owners.has(String(t.id))).flatMap(t => t.players).filter(p => allowed.includes(p.position));
      select.innerHTML = '<option value="">Player TBD</option>' + players.sort((a,b)=>a.name.localeCompare(b.name)).map(p=>`<option value="${escapeHTML(p.id)}">${escapeHTML(p.name)} — ${escapeHTML(p.ownerTeamName)}</option>`).join('');
      select.value = players.some(p => String(p.id) === String(previous)) ? String(previous) : '';
      selection.id = select.value || null;
    });
  }
}
async function init() {
  try {
    config = await load('data/matchup.json');
    snapshot = await load(`data/rosters-${config.season}.json`);
    document.getElementById('week').value = config.week || '';
    document.getElementById('enabled').checked = config.enabled;
    document.getElementById('teams').innerHTML = snapshot.teams.map(t => `<label>${escapeHTML(t.name)} <select data-team="${escapeHTML(t.id)}"><option value="">Unassigned</option><option value="west">West</option><option value="east">East</option></select></label>`).join('');
    document.querySelectorAll('[data-team]').forEach(select => {
      select.value = ['west','east'].find(side => config.sides[side].teamIds.map(String).includes(select.dataset.team)) || '';
      select.addEventListener('change', () => {
        for (const side of ['west','east']) config.sides[side].teamIds = [...document.querySelectorAll('[data-team]')].filter(s => s.value === side).map(s => Number(s.dataset.team));
        populatePlayers();
      });
    });
    for (const side of ['west','east']) {
      document.getElementById(side).innerHTML = config.sides[side].players.map((p,i)=>`<label>${escapeHTML(p.slot)} <select id="${side}-${i}"></select></label>`).join('');
      config.sides[side].players.forEach((p,i) => document.getElementById(`${side}-${i}`).addEventListener('change',event=>{p.id=event.target.value || null;}));
    }
    populatePlayers();
    document.getElementById('status').textContent = snapshot.capturedAt ? `Using the ${config.season} roster snapshot captured ${new Date(snapshot.capturedAt).toLocaleString()}. Ownership stays fixed until the snapshot is explicitly replaced.` : 'The annual roster query needs to run before teams or players can be selected. Pro Bowl players can remain TBD.';
  } catch(error) { document.getElementById('status').textContent = error.message; }
}
document.getElementById('setup').addEventListener('submit',event=>{
  event.preventDefault();
  if (!config || !snapshot) return;
  const week = document.getElementById('week').value;
  config.week = week ? Number(week) : null;
  config.enabled = document.getElementById('enabled').checked;
  const selected = Object.values(config.sides).flatMap(s=>s.players).map(p=>p.id).filter(Boolean);
  let error = '';
  if (new Set(selected).size !== selected.length) error = 'A player can only be selected once.';
  if (Object.values(config.sides).some(s=>s.teamIds.length>6)) error = 'Each side can contain at most six teams.';
  if (config.enabled && (!config.week || Object.values(config.sides).some(s=>s.teamIds.length!==6 || s.players.some(p=>!p.id)))) error = 'Choose a week, six teams per side, and every player before enabling score refreshes.';
  if (error) {document.getElementById('status').textContent=error;return;}
  const url = URL.createObjectURL(new Blob([JSON.stringify(config,null,2)+'\n'],{type:'application/json'}));
  const link = document.createElement('a');link.href=url;link.download=`pro-bowl-setup-${config.season}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  document.getElementById('status').textContent = 'Setup exported. Import the file to apply it to the shared scoreboard.';
});
init();

'use strict';
const dataBase = location.hostname.endsWith('.github.io')
  ? 'https://raw.githubusercontent.com/MattHCoding/Madison-Fantasy-League-Pro-Bowl-Scoreboard/main/' : './';
let config, snapshot, originalConfig, saving = false;
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
      const source = snapshot.teams.length ? snapshot.teams.filter(t => owners.has(String(t.id))).flatMap(t => t.players) : config.sides[side].players.map(p => config.selectedPlayers?.[String(p.id)]).filter(Boolean);
      const players = source.filter(p => allowed.includes(p.position));
      select.innerHTML = '<option value="">Player TBD</option>' + players.sort((a,b)=>a.name.localeCompare(b.name)).map(p=>`<option value="${escapeHTML(p.id)}">${escapeHTML(p.name)} — ${escapeHTML(p.ownerTeamName || 'Owner not yet linked')}</option>`).join('');
      select.value = players.some(p => String(p.id) === String(previous)) ? String(previous) : '';
      selection.id = select.value || null;
    });
  }
}
async function init() {
  try {
    config = location.hostname.endsWith('.github.io') ? (await setupStore.read()).config : await load('data/matchup.json');
    originalConfig = structuredClone(config);
    snapshot = await load(`data/rosters-${config.season}.json`);
    document.getElementById('week').value = config.week || '';
    document.getElementById('enabled').checked = config.enabled;
    document.getElementById('teams').innerHTML = snapshot.teams.map(t => `<label>${escapeHTML(t.name)} <select data-team="${escapeHTML(t.id)}"><option value="">Unassigned</option><option value="west">${escapeHTML(config.sides.west.name || 'West')}</option><option value="east">${escapeHTML(config.sides.east.name || 'East')}</option></select></label>`).join('');
    document.querySelectorAll('[data-team]').forEach(select => {
      select.value = ['west','east'].find(side => config.sides[side].teamIds.map(String).includes(select.dataset.team)) || '';
      select.addEventListener('change', () => {
        for (const side of ['west','east']) config.sides[side].teamIds = [...document.querySelectorAll('[data-team]')].filter(s => s.value === side).map(s => Number(s.dataset.team));
        populatePlayers();
      });
    });
    for (const side of ['west','east']) {
      document.getElementById(side).closest('fieldset').querySelector('legend').textContent = `${config.sides[side].name || (side === 'west' ? 'Team West' : 'Team East')} selections`;
      document.getElementById(side).innerHTML = config.sides[side].players.map((p,i)=>`<label>${escapeHTML(p.slot)} <select id="${side}-${i}"></select></label>`).join('');
      config.sides[side].players.forEach((p,i) => document.getElementById(`${side}-${i}`).addEventListener('change',event=>{p.id=event.target.value || null;}));
    }
    populatePlayers();
    document.getElementById('status').textContent = snapshot.capturedAt ? `Using the ${config.season} roster snapshot captured ${new Date(snapshot.capturedAt).toLocaleString()}. Ownership stays fixed until the snapshot is explicitly replaced.` : (Object.keys(config.selectedPlayers || {}).length ? 'Selected Pro Bowl lineups are loaded. Run the annual roster query to link fantasy owners and assign the six-team sides.' : 'The annual roster query needs to run before teams or players can be selected. Pro Bowl players can remain TBD.');
  } catch(error) { document.getElementById('status').textContent = error.message; }
}
document.getElementById('setup').addEventListener('submit',async event=>{
  event.preventDefault();
  if (!config || !snapshot || saving) return;
  const draft = structuredClone(config);
  const week = document.getElementById('week').value;
  draft.week = week ? Number(week) : null;
  draft.enabled = document.getElementById('enabled').checked;
  const status = document.getElementById('status');
  const tokenInput = document.getElementById('github-token');
  const token = tokenInput.value.trim();
  try {
    setupStore.validate(draft,snapshot);
    if (!token) {
      document.getElementById('connection').open = true;
      tokenInput.focus();
      throw new Error('Connect GitHub below before submitting.');
    }
    saving = true;
    const controls = [...document.querySelectorAll('#setup input, #setup select, #setup button')];
    controls.forEach(control=>{control.disabled=true;});
    status.textContent = 'Saving selections to the shared scoreboard…';
    try {
      await setupStore.save(draft,originalConfig,token);
      config.week = draft.week;config.enabled = draft.enabled;
      originalConfig = structuredClone(draft);
      status.textContent = 'Saved to GitHub. The live scoreboard will pick up these selections on its next refresh (within about a minute).';
      document.getElementById('view-scoreboard').hidden = false;
    } finally {
      controls.forEach(control=>{control.disabled=false;});
      saving = false;
    }
  } catch(error) {status.textContent=error.message;}
});
init();

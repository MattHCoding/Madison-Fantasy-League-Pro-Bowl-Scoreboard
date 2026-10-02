'use strict';
// GitHub is the shared store. Authentication stays in the open page only.
const setupStore = (() => {
  const endpoint = 'https://api.github.com/repos/MattHCoding/Madison-Fantasy-League-Pro-Bowl-Scoreboard/contents/data/matchup.json';
  const headers = token => ({Accept:'application/vnd.github+json', 'X-GitHub-Api-Version':'2022-11-28', ...(token ? {Authorization:`Bearer ${token}`} : {})});
  const encode = value => btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value,null,2)+'\n')));
  const decode = value => JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(value.replace(/\s/g,'')),c=>c.charCodeAt(0))));
  async function read(token) {
    const response = await fetch(endpoint + '?ref=main', {headers:headers(token),cache:'no-store'});
    if (!response.ok) throw new Error(response.status === 401 ? 'GitHub token is invalid or expired.' : 'Could not read the shared setup from GitHub. Try again later.');
    const file = await response.json();
    return {config:decode(file.content),sha:file.sha};
  }
  function validate(config, snapshot) {
    if (config.season !== snapshot.season || config.leagueId !== snapshot.leagueId) throw new Error('Roster snapshot does not match this season and league. Reload setup.');
    if (config.week !== null && (!Number.isInteger(config.week) || config.week < 1 || config.week > 18)) throw new Error('Choose a week from 1 to 18.');
    if (config.enabled && !config.week) throw new Error('Choose the matchup week before enabling score refreshes.');
    const teams = new Map(snapshot.teams.map(t=>[String(t.id),t]));
    const players = new Map(config.enabled ? [] : Object.entries(config.selectedPlayers || {}).map(([id,p])=>[id,{player:p,owner:null}]));
    for (const t of snapshot.teams) for (const p of t.players) players.set(String(p.id),{player:p,owner:String(t.id)});
    const usedTeams = new Set(), usedPlayers = new Set();
    for (const key of ['west','east']) {
      const side = config.sides[key];
      if (side.teamIds.length > 6 || (config.enabled && side.teamIds.length !== 6)) throw new Error('Choose six fantasy teams per side before enabling score refreshes.');
      const owners = new Set();
      for (const id of side.teamIds.map(String)) {
        if (!teams.has(id) || usedTeams.has(id)) throw new Error('Each fantasy team must belong to just one side.');
        owners.add(id);usedTeams.add(id);
      }
      if (JSON.stringify(side.players.map(p=>p.slot)) !== JSON.stringify(config.slots)) throw new Error('Selections must match the configured lineup slots. Reload setup.');
      for (const selection of side.players) {
        if (selection.id === null) {
          if (config.enabled) throw new Error('Choose every player before enabling score refreshes.');
          continue;
        }
        const id = String(selection.id), entry = players.get(id);
        if (usedPlayers.has(id)) throw new Error('A player can only be selected once.');
        if (!entry) throw new Error('Run the annual roster query to link players before enabling score refreshes.');
        const allowed = selection.slot === 'FLEX' ? ['RB','WR','TE'] : [selection.slot];
        if (!allowed.includes(entry.player.position) || (entry.owner !== null && !owners.has(entry.owner))) throw new Error('Player must belong to this side and be eligible for the slot.');
        usedPlayers.add(id);
      }
    }
  }
  async function save(config, original, token) {
    if (!token) throw new Error('Connect GitHub below before submitting.');
    const latest = await read(token);
    if (JSON.stringify(latest.config) !== JSON.stringify(original)) throw new Error('The shared setup changed since you opened this page. Reload before submitting; your selections have not been saved.');
    let response;
    try {
      response = await fetch(endpoint, {method:'PUT',headers:{...headers(token),'Content-Type':'application/json'},body:JSON.stringify({message:'Update shared Pro Bowl selections',content:encode(config),sha:latest.sha,branch:'main'})});
    } catch {
      throw new Error('Could not confirm the save. Check the scoreboard or reload setup before retrying.');
    }
    if (!response.ok) {
      if (response.status === 409) throw new Error('The shared setup changed during saving. Reload before submitting again.');
      if (response.status === 401) throw new Error('GitHub token is invalid or expired.');
      if (response.status === 403 || response.status === 404) throw new Error('GitHub access was denied. Give the token Contents: Read and write access to this repository.');
      throw new Error('GitHub could not save the setup. Check repository permissions and try again later.');
    }
    return response.json();
  }
  return {read,validate,save};
})();

'use strict';
const dataBase = location.hostname.endsWith('.github.io')
  ? 'https://raw.githubusercontent.com/MattHCoding/Madison-Fantasy-League-Pro-Bowl-Scoreboard/main/' : './';
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const points = value => Number.isFinite(value) ? value.toFixed(2) : '—';
async function loadJSON(path) {
  const response = await fetch(`${dataBase}${path}?refresh=${Date.now()}`, {cache: 'no-store'});
  if (!response.ok) throw new Error('Could not load scoreboard data.');
  return response.json();
}
let refreshing = false;
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const config = await loadJSON('data/matchup.json');
    const [snapshot, scores] = await Promise.all([loadJSON(`data/rosters-${config.season}.json`), loadJSON('data/scores.json')]);
    const pool = new Map([...Object.entries(config.selectedPlayers || {}), ...snapshot.teams.flatMap(t => t.players.map(p => [String(p.id), p]))]);
    const compatible = scores.season === config.season && scores.week === config.week && scores.leagueId === config.leagueId;
    document.title = `Madison Fantasy Pro Bowl • ${config.season}`;
    document.getElementById('week-info').textContent = `${config.season} Season • ${config.week ? `Week ${config.week}` : 'Week TBD'}`;
    for (const key of ['west', 'east']) {
      document.getElementById(`${key}-players`).closest('.team-column').querySelector('.team-name').textContent = config.sides[key].name || (key === 'west' ? 'Team West' : 'Team East');
      let actual = 0, projected = 0, actualComplete = true, projectedComplete = true;
      document.getElementById(`${key}-players`).innerHTML = config.sides[key].players.map(selection => {
        const player = pool.get(String(selection.id));
        const score = compatible && player ? scores.players[String(selection.id)] : null;
        if (!score || !Number.isFinite(score.actual)) actualComplete = false;
        else actual += score.actual;
        const estimate = projectedPoints(score,config.pointsRemainingExponent ?? 1);
        if (!Number.isFinite(estimate)) projectedComplete = false;
        else projected += estimate;
        const rowClass = score?.state === 'post' ? 'is-complete' : score?.state === 'in' ? 'is-playing' : '';
        const detail = score?.game?.detail || (score?.state === 'bye' ? 'No game this week' : '');
        return `<div class="player-row ${rowClass}"><span class="position ${escapeHTML(selection.slot)}">${escapeHTML(selection.slot)}</span><div><div class="player-name">${escapeHTML(player?.name || 'Player TBD')}</div><div class="owner">${escapeHTML(player?.ownerTeamName || 'Fantasy owner not yet linked')}</div><div class="game-detail">${escapeHTML(detail)}${score?.injuryStatus ? ` • ${escapeHTML(score.injuryStatus)}` : ''}</div></div><div class="points-actual">${points(score?.actual)}</div><div class="points-projected" title="Projected final fantasy score">${points(estimate)}</div></div>`;
      }).join('');
      document.getElementById(`${key}-actual`).textContent = actualComplete ? points(actual) : '—';
      document.getElementById(`${key}-projected`).textContent = projectedComplete ? points(projected) : '—';
    }
    const probabilities = compatible ? simulateWinProbability(
      config.sides.west.players.map(p=>scores.players[String(p.id)]),
      config.sides.east.players.map(p=>scores.players[String(p.id)]),
      config.pointsRemainingExponent ?? 1
    ) : null;
    for (const side of ['west','east']) {
      document.getElementById(`${side}-win-probability`).textContent = probabilities ? `${(100*probabilities[side]).toFixed(1)}%` : '—';
      document.getElementById(`${side}-miles`).textContent = probabilities ? String(Math.round((1-probabilities[side])*100)) : '—';
    }
    const probabilityBar = document.getElementById('header-probability-bar');
    const headerLabels = {};
    for (const side of ['west','east']) {
      const name = config.sides[side].name || (side === 'west' ? 'Team West' : 'Team East');
      headerLabels[side] = `${name} ${probabilities ? `${(100*probabilities[side]).toFixed(1)}%` : '—'}`;
      document.getElementById(`header-${side}-probability`).textContent = headerLabels[side];
      document.getElementById(`header-${side}-fill`).style.width = probabilities ? `${100*probabilities[side]}%` : '0%';
    }
    document.getElementById('header-tie-fill').style.width = probabilities ? `${100*probabilities.tie}%` : '0%';
    const tieLabel = document.getElementById('header-tie-probability');
    tieLabel.hidden = !probabilities || probabilities.tie === 0;
    tieLabel.textContent = probabilities ? `Tie ${(100*probabilities.tie).toFixed(1)}%` : '';
    probabilityBar.classList.toggle('is-unavailable',!probabilities);
    probabilityBar.setAttribute('aria-label',probabilities
      ? `${headerLabels.west}; ${headerLabels.east}; tie ${(100*probabilities.tie).toFixed(1)}%`
      : 'Win probabilities unavailable');
    let message = snapshot.capturedAt ? `Roster snapshot: ${new Date(snapshot.capturedAt).toLocaleDateString()}.` : (Object.keys(config.selectedPlayers || {}).length ? 'Pro Bowl lineups loaded. Fantasy owners have not been linked yet.' : 'Annual fantasy roster snapshot has not been loaded yet.');
    if (!config.enabled) message += ' Score refreshes are paused.';
    else if (compatible && scores.updatedAt) {
      const age = Date.now() - Date.parse(scores.updatedAt);
      message += ` Scores updated ${new Date(scores.updatedAt).toLocaleString()}.`;
      if (age > 10 * 60 * 1000) message += ' Updates are delayed; showing the last successful refresh.';
    } else message += ' Waiting for the first ESPN score update; the refresh workflow must have valid ESPN credentials.';
    document.getElementById('status').textContent = message;
    const gameContainer = document.getElementById('games-grid');
    gameContainer.innerHTML = compatible && scores.games?.length ? scores.games.map(game => `<article class="game-card ${game.state === 'in' ? 'live' : ''}"><div class="game-time">${escapeHTML(game.detail)}</div>${game.teams.map(t => `<div class="game-team"><span>${escapeHTML(t.name)}</span><strong>${game.state === 'pre' ? '—' : escapeHTML(t.score)}</strong></div>`).join('')}</article>`).join('') : '<p>Games will appear when the matchup is enabled.</p>';
  } catch (error) {
    document.getElementById('status').textContent = `${error.message} Showing the last loaded scoreboard. Retrying automatically.`;
  } finally { refreshing = false; }
}
document.getElementById('refresh').addEventListener('click', refresh);
refresh();
setInterval(refresh, 60000);

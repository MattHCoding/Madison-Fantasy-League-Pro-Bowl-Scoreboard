"""Read-only ESPN helpers. Never persist raw responses or authentication cookies."""
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DEF'}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def get_json(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'ESPN returned HTTP {error.code}; check the saved ESPN credentials.') from None


def league_query(config, views, week=None, player_ids=None):
    swid, s2 = os.environ.get('ESPN_SWID'), os.environ.get('ESPN_S2')
    if not swid or not s2:
        raise RuntimeError('Set ESPN_SWID and ESPN_S2 in the environment or GitHub Actions secrets.')
    if any(c in swid + s2 for c in '\r\n;'):
        raise ValueError('Invalid cookie value.')
    params = [('view', view) for view in views]
    if week is not None:
        params.append(('scoringPeriodId', week))
    headers = {'Cookie': f'SWID={swid}; espn_s2={s2}', 'Accept': 'application/json'}
    if player_ids is not None:
        stat_codes = [f"00{config['season']}", f"10{config['season']}"]
        if week is not None:
            # Weekly projections are not included by the season-only codes.
            stat_codes.append(f"11{config['season']}{week}")
        headers['x-fantasy-filter'] = json.dumps({'players': {
            'filterIds': {'value': [int(i) for i in player_ids]},
            'filterStatsForTopScoringPeriodIds': {'value': 18, 'additionalValue': stat_codes},
        }})
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{config['season']}/segments/0/leagues/{config['leagueId']}?{urllib.parse.urlencode(params)}"
    return get_json(url, headers)


def unpack(entry):
    return entry.get('playerPoolEntry', entry).get('player', {})


def stat_points(player, season, week, source):
    matches = [s for s in player.get('stats', []) if s.get('scoringPeriodId') == week and s.get('statSourceId') == source and s.get('statSplitTypeId') == 1 and s.get('seasonId', season) == season]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous weekly stats for ESPN player {player.get('id')}")
    if not matches:
        return None
    value = matches[0].get('appliedTotal')
    return float(value) if isinstance(value, (float, int)) and math.isfinite(value) else None


def validate(config, snapshot, complete=False):
    if config['season'] != snapshot['season'] or config['leagueId'] != snapshot['leagueId']:
        raise ValueError('Roster snapshot does not match this season and league.')
    week = config.get('week')
    if week is not None and (type(week) is not int or not 1 <= week <= 18):
        raise ValueError('Choose an NFL regular-season week from 1 to 18.')
    if complete and week is None:
        raise ValueError('Set the matchup week before enabling refreshes.')
    teams = {str(t['id']): t for t in snapshot['teams']}
    players = {str(p['id']): (p, str(t['id'])) for t in snapshot['teams'] for p in t['players']}
    used_teams, used_players = set(), set()
    for key in ('west', 'east'):
        side = config['sides'][key]
        team_ids = list(map(str, side['teamIds']))
        if len(set(team_ids)) != len(team_ids) or any(i not in teams or i in used_teams for i in team_ids):
            raise ValueError('Each fantasy team must belong to just one side.')
        if len(team_ids) > 6 or (complete and len(team_ids) != 6):
            raise ValueError('Each side must have six fantasy teams.')
        used_teams.update(team_ids)
        if [p['slot'] for p in side['players']] != config['slots']:
            raise ValueError('Selections must match the configured lineup slots.')
        for selection in side['players']:
            pid = selection['id']
            if pid is None:
                if complete:
                    raise ValueError('Select every Pro Bowl slot before enabling refreshes.')
                continue
            pid = str(pid)
            if pid not in players or pid in used_players:
                raise ValueError('Unknown or duplicate Pro Bowl player.')
            player, owner = players[pid]
            allowed = ('RB', 'WR', 'TE') if selection['slot'] == 'FLEX' else (selection['slot'],)
            if owner not in team_ids or player['position'] not in allowed:
                raise ValueError('Player must belong to this side and be eligible for the slot.')
            used_players.add(pid)
    return players

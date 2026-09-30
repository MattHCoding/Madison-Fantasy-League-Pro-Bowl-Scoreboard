"""Explicit annual snapshot query; never invoked by score refreshes."""
import argparse
from espn import ROOT, POSITIONS, league_query, now, read, unpack, write


def build_snapshot(config, data):
    teams = []
    for team in data.get('teams', []):
        name = team.get('name') or ' '.join(filter(None, [team.get('location'), team.get('nickname')])) or team.get('abbrev') or f"Team {team['id']}"
        players = []
        for entry in team.get('roster', {}).get('entries', []):
            player = unpack(entry)
            if not player or player.get('defaultPositionId') not in POSITIONS:
                continue
            players.append({'id': str(player['id']), 'name': player['fullName'], 'position': POSITIONS[player['defaultPositionId']], 'proTeamId': player.get('proTeamId'), 'ownerTeamId': team['id'], 'ownerTeamName': name})
        teams.append({'id': team['id'], 'name': name, 'divisionId': team.get('divisionId'), 'players': players})
    if len(teams) != 12 or not all(t['players'] for t in teams):
        raise ValueError('Expected twelve nonempty fantasy rosters; leaving the existing snapshot untouched.')
    return {'season': config['season'], 'leagueId': config['leagueId'], 'capturedAt': now(), 'teams': teams}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replace', action='store_true', help='Explicitly replace a previously captured snapshot')
    args = parser.parse_args()
    config = read(ROOT / 'data/matchup.json')
    path = ROOT / f"data/rosters-{config['season']}.json"
    if path.exists() and read(path).get('capturedAt') and not args.replace:
        raise ValueError('This season already has a snapshot. Use --replace only for an intentional ownership update.')
    data = league_query(config, ['mTeam', 'mRoster'])
    write(path, build_snapshot(config, data))
    print(f"Stored twelve fantasy rosters for {config['season']}; no scores or selections changed.")


if __name__ == '__main__':
    main()

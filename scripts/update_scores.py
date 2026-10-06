"""Query scores/projections for selected IDs; never reads current fantasy rosters."""
import argparse
import math
from datetime import datetime, timezone, timedelta
from espn import ROOT, get_json, league_query, now, read, stat_points, unpack, validate, write


def time_remaining(status):
    """Fraction of regulation remaining from ESPN's game clock; no wall-clock guessing."""
    state = status.get('type', {}).get('state')
    if status.get('type', {}).get('completed') or state == 'post':
        return 0.0
    if state == 'pre':
        return 1.0
    period = status.get('period')
    if state != 'in' or type(period) is not int or period < 1:
        return None
    if period > 4:
        return 0.0  # Regulation is over; the simple model adds no overtime baseline.
    clock = status.get('displayClock')
    try:
        minutes, seconds = map(int, clock.split(':'))
        if not 0 <= minutes <= 15 or not 0 <= seconds < 60:
            return None
        remaining = minutes * 60 + seconds
        if remaining > 900:
            return None
    except (AttributeError, TypeError, ValueError):
        remaining = status.get('clock')
        if type(remaining) not in (int, float) or not 0 <= remaining <= 900:
            return None
    return ((4 - period) * 900 + remaining) / 3600


def points_remaining_fraction(remaining, exponent=1):
    return None if remaining is None else max(0.0, min(1.0, remaining)) ** exponent


def projected_points(actual, initial, remaining):
    if actual is None or remaining is None:
        return None
    if remaining == 0:
        return actual
    return None if initial is None else actual + remaining * initial


def game_map(board):
    result, games = {}, []
    for event in board.get('events', []):
        comp = event['competitions'][0]
        status = comp.get('status', event.get('status', {}))
        state = status.get('type', {}).get('state', 'unknown')
        game = {'id': str(event['id']), 'state': state, 'completed': bool(status.get('type', {}).get('completed')), 'detail': status.get('type', {}).get('shortDetail', ''), 'date': event.get('date'), 'teams': [{'id': str(t['team']['id']), 'name': t['team']['abbreviation'], 'score': t.get('score'), 'homeAway': t.get('homeAway')} for t in comp['competitors']]}
        game.update(period=status.get('period'), displayClock=status.get('displayClock'), timeRemainingFraction=time_remaining(status))
        games.append(game)
        for team in game['teams']:
            result[team['id']] = game
    return result, games


def build_scores(config, snapshot, data, board, previous):
    pool = validate(config, snapshot, complete=True)
    by_team, games = game_map(board)
    current = {str(unpack(p)['id']): unpack(p) for p in data.get('players', []) if unpack(p)}
    same_period = previous.get('season') == config['season'] and previous.get('week') == config['week'] and previous.get('leagueId') == config['leagueId']
    rows = {}
    for side in config['sides'].values():
        for selection in side['players']:
            pid = str(selection['id'])
            player = current.get(pid)
            if player is None:
                raise ValueError('ESPN did not return every selected player; preserving the last successful scores.')
            game = by_team.get(str(player.get('proTeamId', pool[pid][0]['proTeamId'])))
            state = 'bye' if game is None else 'post' if game['completed'] else game['state']
            actual = stat_points(player, config['season'], config['week'], 0)
            if actual is None and state in ('pre', 'bye'):
                actual = 0.0
            projection = stat_points(player, config['season'], config['week'], 1)
            old = previous.get('players', {}).get(pid, {}) if same_period else {}
            # Update pregame projections, then freeze the last captured baseline at kickoff.
            initial = old.get('initialProjection') if state != 'pre' and old.get('initialProjection') is not None else projection
            captured_before_kickoff = state == 'pre' or (bool(old.get('capturedBeforeKickoff')) and old.get('initialProjection') is not None)
            remaining = 0.0 if state == 'bye' else game['timeRemainingFraction']
            points_fraction = points_remaining_fraction(remaining, config.get('pointsRemainingExponent', 1))
            rows[pid] = {'actual': actual, 'initialProjection': initial, 'capturedBeforeKickoff': captured_before_kickoff, 'espnWeeklyProjection': projection, 'liveProjection': projected_points(actual, initial, points_fraction), 'pointsRemainingFraction': points_fraction, 'timeRemainingFraction': remaining, 'state': state, 'game': game, 'injuryStatus': player.get('injuryStatus')}
    return {'season': config['season'], 'leagueId': config['leagueId'], 'week': config['week'], 'updatedAt': now(), 'projectionSource': 'ESPN fantasy weekly appliedTotal', 'liveProjectionModel': 'actual + timeRemainingFraction ** pointsRemainingExponent * initialProjection', 'pointsRemainingExponent': config.get('pointsRemainingExponent', 1), 'players': rows, 'games': games}


def selected_scores_final(config, pool, ids, board, previous):
    """Stop polling only after final scores for this selection have been saved."""
    if not ids or any(previous.get(key) != config[key] for key in ('season', 'leagueId', 'week')):
        return False
    by_team, games = game_map(board)
    by_id = {game['id']: game for game in games}
    rows = previous.get('players', {})
    if set(rows) != set(ids):
        return False
    for pid in ids:
        row = rows[pid]
        actual = row.get('actual')
        if type(actual) not in (int, float) or not math.isfinite(actual):
            return False
        if row.get('state') == 'bye':
            team = pool[pid][0].get('proTeamId')
            if team in (None, 0, '0') or str(team) in by_team or row.get('game') is not None:
                return False
        elif row.get('state') == 'post':
            saved_game = row.get('game') or {}
            game = by_id.get(str(saved_game.get('id')))
            if not saved_game.get('completed') or game is None or not game['completed']:
                return False
        else:
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scheduled', action='store_true')
    args = parser.parse_args()
    config = read(ROOT / 'data/matchup.json')
    if not config.get('enabled'):
        print('Matchup is not enabled; no ESPN requests made.')
        return
    snapshot = read(ROOT / f"data/rosters-{config['season']}.json")
    pool = validate(config, snapshot, complete=True)
    ids = [str(p['id']) for side in config['sides'].values() for p in side['players']]
    board = get_json(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={config['season']}&seasontype=2&week={config['week']}")
    if not board.get('events'):
        raise ValueError('No schedule returned; preserving the last successful scores.')
    path = ROOT / 'data/scores.json'
    previous = read(path) if path.exists() else {}
    if args.scheduled:
        if selected_scores_final(config, pool, ids, board, previous):
            print('Every selected player is final or on bye; no fantasy score query made.')
            return
        events = board['events']
        starts = [datetime.fromisoformat(event['date'].replace('Z', '+00:00')) for event in events]
        clock = datetime.now(timezone.utc)
        finals = all(event['competitions'][0].get('status', event.get('status', {})).get('type', {}).get('completed') for event in events)
        if min(starts) > clock + timedelta(hours=24) or (finals and max(starts) < clock - timedelta(hours=48)):
            print('Outside the matchup refresh window; no fantasy score query made.')
            return
    data = league_query(config, ['kona_playercard'], config['week'], ids)
    write(path, build_scores(config, snapshot, data, board, previous))
    print('Updated selected player scores and ESPN initial projections.')


if __name__ == '__main__':
    main()

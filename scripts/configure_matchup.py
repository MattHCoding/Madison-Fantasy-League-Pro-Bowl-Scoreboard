"""Apply an exported annual setup without accepting arbitrary extra fields."""
import argparse
from espn import ROOT, read, validate, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    args = parser.parse_args()
    from pathlib import Path
    incoming = read(Path(args.file))
    current = read(ROOT / 'data/matchup.json')
    if incoming.get('season') != current['season'] or incoming.get('leagueId') != current['leagueId']:
        raise ValueError('Setup must match the configured season and league.')
    config = {k: current[k] for k in ('season', 'leagueId', 'slots')}
    config.update(week=incoming.get('week'), enabled=incoming.get('enabled') is True, sides={key: {'teamIds': incoming['sides'][key]['teamIds'], 'players': [{'slot': p['slot'], 'id': str(p['id']) if p['id'] is not None else None} for p in incoming['sides'][key]['players']]} for key in ('west', 'east')})
    snapshot = read(ROOT / f"data/rosters-{config['season']}.json")
    validate(config, snapshot, complete=config['enabled'])
    write(ROOT / 'data/matchup.json', config)
    print('Saved annual team assignments and Pro Bowl selections.')


if __name__ == '__main__':
    main()

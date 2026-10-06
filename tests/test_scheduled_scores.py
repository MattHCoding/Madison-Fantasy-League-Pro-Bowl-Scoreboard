import copy
import json
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_scores
from test_data import fixture


class ScheduledScoreTests(unittest.TestCase):
    def setUp(self):
        self.config, self.snapshot, self.data, self.board = fixture()
        self.previous = update_scores.build_scores(
            self.config, self.snapshot, self.data, self.board, {})

    def run_refresh(self, scheduled=True, previous=True, error=None):
        with TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'data/matchup.json').write_text(json.dumps(self.config))
            (root / 'data/rosters-2026.json').write_text(json.dumps(self.snapshot))
            path = root / 'data/scores.json'
            if previous:
                path.write_text(json.dumps(self.previous))
            before = path.read_bytes() if path.exists() else None
            stack.enter_context(patch.object(update_scores, 'ROOT', root))
            stack.enter_context(patch.object(sys, 'argv', ['update_scores.py'] + (['--scheduled'] if scheduled else [])))
            clock = stack.enter_context(patch.object(update_scores, 'datetime'))
            clock.fromisoformat.side_effect = datetime.fromisoformat
            clock.now.return_value = datetime(2026, 10, 1, 1, tzinfo=timezone.utc)
            board_query = stack.enter_context(patch.object(update_scores, 'get_json', return_value=self.board))
            query = stack.enter_context(patch.object(update_scores, 'league_query', return_value=self.data))
            write = stack.enter_context(patch.object(update_scores, 'write', wraps=update_scores.write))
            if error:
                with self.assertRaises(error):
                    update_scores.main()
            else:
                update_scores.main()
            after = path.read_bytes() if path.exists() else None
            return query.call_count, write.call_count, before, after, board_query.call_count

    def assert_noop(self):
        queries, writes, before, after, boards = self.run_refresh()
        self.assertEqual((queries, writes, boards), (0, 0, 1))
        self.assertEqual(after, before)

    def assert_refresh(self, **kwargs):
        queries, writes, _, _, _ = self.run_refresh(**kwargs)
        self.assertEqual((queries, writes), (1, 1))

    def test_saved_final_scores_noop_within_48_hours(self):
        self.assert_noop()

    def test_unselected_live_game_does_not_keep_fantasy_polling(self):
        unrelated = copy.deepcopy(self.board['events'][0])
        unrelated['id'] = '901'
        unrelated['competitions'][0]['status']['type'].update(state='in', completed=False)
        for team in unrelated['competitions'][0]['competitors']:
            team['team']['id'] = str(int(team['team']['id']) + 10)
        self.board['events'].append(unrelated)
        self.assert_noop()

    def test_final_and_bye_scores_noop(self):
        self.snapshot['teams'][6]['players'][0]['proTeamId'] = 3
        self.data['players'][1]['player']['proTeamId'] = 3
        self.previous = update_scores.build_scores(
            self.config, self.snapshot, self.data, self.board, {})
        self.assertEqual(self.previous['players']['102']['state'], 'bye')
        self.assert_noop()

    def test_all_byes_noop(self):
        for team in self.snapshot['teams']:
            for player in team['players']:
                player['proTeamId'] += 10
        for entry in self.data['players']:
            entry['player']['proTeamId'] += 10
        self.previous = update_scores.build_scores(
            self.config, self.snapshot, self.data, self.board, {})
        self.assert_noop()

    def test_manual_refresh_queries_even_when_saved_scores_are_final(self):
        self.assert_refresh(scheduled=False)

    def test_first_postgame_run_captures_final_fantasy_scores(self):
        self.previous['players']['101'].update(state='in', actual=10)
        self.assert_refresh()
        self.assert_noop_after_capture()

    def assert_noop_after_capture(self):
        self.previous = update_scores.build_scores(
            self.config, self.snapshot, self.data, self.board, self.previous)
        self.assert_noop()

    def test_missing_score_file_or_player_still_refreshes(self):
        self.assert_refresh(previous=False)
        del self.previous['players']['101']
        self.assert_refresh()

    def test_missing_or_invalid_final_actual_still_refreshes(self):
        for actual in (None, '30', True, float('nan'), float('inf')):
            with self.subTest(actual=actual):
                self.previous['players']['101']['actual'] = actual
                self.assert_refresh()

    def test_zero_and_negative_final_actuals_allow_noop(self):
        self.previous['players']['101']['actual'] = 0
        self.previous['players']['102']['actual'] = -2
        self.assert_noop()

    def test_stale_period_or_selection_still_refreshes(self):
        for key in ('season', 'leagueId', 'week'):
            with self.subTest(key=key):
                original = self.previous[key]
                self.previous[key] += 1
                self.assert_refresh()
                self.previous[key] = original
        self.previous['players']['999'] = self.previous['players'].pop('101')
        self.assert_refresh()

    def test_current_game_must_still_be_final(self):
        status = self.board['events'][0]['competitions'][0]['status']['type']
        for state in ('pre', 'in', 'unknown', 'post'):
            with self.subTest(state=state):
                status.update(state=state, completed=False)
                self.assert_refresh()

    def test_final_game_identity_and_completion_must_match(self):
        saved = self.previous['players']['101']['game']
        saved['id'] = 'old-game'
        self.assert_refresh()
        saved['id'] = '900'
        saved['completed'] = False
        self.assert_refresh()

    def test_bye_with_a_current_game_still_refreshes(self):
        self.previous['players']['101'].update(state='bye', game=None)
        self.assert_refresh()

    def test_unknown_team_is_not_assumed_to_be_a_bye(self):
        self.previous['players']['101'].update(state='bye', game=None)
        for team_id in (None, 0, '0'):
            with self.subTest(team_id=team_id):
                self.snapshot['teams'][0]['players'][0]['proTeamId'] = team_id
                self.assert_refresh()

    def test_empty_schedule_fails_without_overwriting_scores(self):
        self.board['events'] = []
        queries, writes, before, after, _ = self.run_refresh(error=ValueError)
        self.assertEqual((queries, writes), (0, 0))
        self.assertEqual(after, before)

    def test_partial_fantasy_response_preserves_previous_scores(self):
        self.previous['players']['101']['state'] = 'in'
        self.data['players'].pop()
        queries, writes, before, after, _ = self.run_refresh(error=ValueError)
        self.assertEqual((queries, writes), (1, 0))
        self.assertEqual(after, before)

    def test_existing_refresh_window_still_applies(self):
        self.previous['players']['101']['state'] = 'in'
        for date in ('2026-10-03T00:00Z', '2026-09-28T00:00Z'):
            with self.subTest(date=date):
                self.board['events'][0]['date'] = date
                queries, writes, before, after, _ = self.run_refresh()
                self.assertEqual((queries, writes), (0, 0))
                self.assertEqual(after, before)

    def test_disabled_matchup_makes_no_requests(self):
        self.config['enabled'] = False
        queries, writes, before, after, boards = self.run_refresh()
        self.assertEqual((queries, writes, boards), (0, 0, 0))
        self.assertEqual(after, before)

    def test_invalid_roster_still_fails_before_requests(self):
        self.snapshot['leagueId'] += 1
        queries, writes, before, after, boards = self.run_refresh(error=ValueError)
        self.assertEqual((queries, writes, boards), (0, 0, 0))
        self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()

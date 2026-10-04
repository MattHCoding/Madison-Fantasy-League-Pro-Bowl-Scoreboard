import copy
import json
from unittest.mock import patch
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from espn import stat_points, validate, league_query
from update_scores import build_scores, time_remaining, projected_points, points_remaining_fraction
from update_rosters import build_snapshot


def fixture():
    teams = [{'id': i, 'name': f'Fantasy {i}', 'players': []} for i in range(1, 13)]
    teams[0]['players'] = [{'id': '101', 'name': 'West QB', 'position': 'QB', 'proTeamId': 1, 'ownerTeamName': 'Fantasy 1'}]
    teams[6]['players'] = [{'id': '102', 'name': 'East QB', 'position': 'QB', 'proTeamId': 2, 'ownerTeamName': 'Fantasy 7'}]
    snapshot = {'season': 2026, 'leagueId': 123, 'teams': teams}
    config = {'season': 2026, 'leagueId': 123, 'week': 4, 'enabled': True, 'slots': ['QB'], 'sides': {'west': {'teamIds': list(range(1,7)), 'players': [{'id':'101','slot':'QB'}]}, 'east': {'teamIds': list(range(7,13)), 'players': [{'id':'102','slot':'QB'}]}}}
    def player(pid, pro, actual, projection):
        return {'player': {'id': int(pid), 'proTeamId': pro, 'stats': [{'seasonId':2026,'scoringPeriodId':4,'statSourceId':source,'statSplitTypeId':1,'appliedTotal':points} for source,points in [(0,actual),(1,projection)]]}}
    data = {'players': [player('101',1,30,10),player('102',2,31,30)]}
    board = {'events':[{'id':'900','date':'2026-10-01T00:00Z','competitions':[{'status':{'type':{'state':'post','completed':True,'shortDetail':'Final'}},'competitors':[{'team':{'id':'1','abbreviation':'A'},'score':'20'},{'team':{'id':'2','abbreviation':'B'},'score':'21'}]}]}]}
    return config,snapshot,data,board


class DataTests(unittest.TestCase):
    def test_query_explicitly_requests_weekly_projections(self):
        config = {'season': 2025, 'leagueId': 123}
        with patch.dict('os.environ', {'ESPN_SWID': 'test-swid', 'ESPN_S2': 'test-s2'}):
            with patch('espn.get_json', return_value={}) as request:
                league_query(config, ['kona_playercard'], 4, ['3918298'])
        _, headers = request.call_args.args
        filters = json.loads(headers['x-fantasy-filter'])['players']
        self.assertIn('1120254', filters['filterStatsForTopScoringPeriodIds']['additionalValue'])
        self.assertEqual(filters['filterIds']['value'], [3918298])

    def test_stat_scope_and_negative_scores(self):
        player = {'stats':[{'seasonId':2026,'scoringPeriodId':4,'statSourceId':0,'statSplitTypeId':0,'appliedTotal':999}, {'seasonId':2026,'scoringPeriodId':4,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':-2}]}
        self.assertEqual(stat_points(player,2026,4,0),-2)
        self.assertIsNone(stat_points(player,2026,5,0))

    def test_final_actuals_are_not_adjusted_and_ownership_stays_fixed(self):
        config,snapshot,data,board = fixture()
        untouched=copy.deepcopy(snapshot)
        result=build_scores(config,snapshot,data,board,{})
        self.assertEqual(result['players']['101']['actual'],30)
        self.assertEqual(result['players']['102']['actual'],31)
        self.assertEqual(result['players']['101']['liveProjection'],30)
        self.assertEqual(snapshot,untouched)

    def test_baseline_freezes_after_kickoff(self):
        config,snapshot,data,board=fixture()
        board['events'][0]['competitions'][0]['status']['type'].update(state='pre',completed=False)
        before=build_scores(config,snapshot,data,board,{})
        data['players'][0]['player']['stats'][1]['appliedTotal']=50
        board['events'][0]['competitions'][0]['status']['type'].update(state='in')
        after=build_scores(config,snapshot,data,board,before)
        self.assertEqual(after['players']['101']['initialProjection'],10)
        self.assertTrue(after['players']['101']['capturedBeforeKickoff'])
        config['week']=5
        for p in data['players']:
            for stat in p['player']['stats']:stat['scoringPeriodId']=5
        self.assertEqual(build_scores(config,snapshot,data,board,before)['players']['101']['initialProjection'],50)

    def test_clock_projection_lifecycle(self):
        self.assertEqual(time_remaining({'type':{'state':'pre'}}),1)
        self.assertEqual(time_remaining({'type':{'state':'in'},'period':2,'displayClock':'0:00'}),0.5)
        self.assertEqual(time_remaining({'type':{'state':'in'},'period':4,'displayClock':'15:00'}),0.25)
        self.assertEqual(time_remaining({'type':{'state':'post','completed':True}}),0)
        self.assertEqual(time_remaining({'type':{'state':'in'},'period':5}),0)
        self.assertIsNone(time_remaining({'type':{'state':'in'},'period':2}))
        self.assertEqual(projected_points(10,20,0.5),20)
        self.assertEqual(projected_points(-3,10,0),-3)
        self.assertEqual(projected_points(5,None,0),5)
        self.assertIsNone(projected_points(None,20,0.5))

    def test_score_rows_use_the_clock_and_preserve_initial(self):
        config,snapshot,data,board=fixture()
        board['events'][0]['competitions'][0]['status'].update(type={'state':'in','completed':False},period=3,displayClock='15:00')
        result=build_scores(config,snapshot,data,board,{})
        self.assertEqual(result['players']['101']['timeRemainingFraction'],0.5)
        self.assertEqual(result['players']['101']['liveProjection'],35)
        self.assertEqual(result['players']['101']['initialProjection'],10)

    def test_shared_curve_matches_browser_means(self):
        self.assertEqual(points_remaining_fraction(0.7),0.7)
        self.assertEqual(points_remaining_fraction(0.5,2),0.25)
        config,snapshot,data,board=fixture()
        config['pointsRemainingExponent']=2
        board['events'][0]['competitions'][0]['status'].update(type={'state':'in','completed':False},period=3,displayClock='15:00')
        data['players'][0]['player']['stats'][1]['appliedTotal']=-20
        result=build_scores(config,snapshot,data,board,{})
        self.assertEqual(result['players']['101']['pointsRemainingFraction'],0.25)
        self.assertEqual(result['players']['101']['liveProjection'],25)

    def test_partial_response_fails(self):
        config,snapshot,data,board=fixture()
        data['players'].pop()
        with self.assertRaises(ValueError):build_scores(config,snapshot,data,board,{})

    def test_missing_live_actual_is_unknown(self):
        config,snapshot,data,board=fixture()
        data['players'][0]['player']['stats'].pop(0)
        self.assertIsNone(build_scores(config,snapshot,data,board,{})['players']['101']['actual'])

    def test_ownership_does_not_require_manual_side_assignment(self):
        config,snapshot,data,board=fixture()
        for side in config['sides'].values():side['teamIds']=[]
        self.assertEqual(build_scores(config,snapshot,data,board,{})['players']['101']['actual'],30)
        config['sides']['west']['players'][0]['id']='102'
        config['sides']['east']['players'][0]['id']='101'
        validate(config,snapshot,True)

    def test_selected_metadata_can_enable_before_snapshot_capture(self):
        config,snapshot,_,_=fixture()
        config['selectedPlayers']={p['id']:p for t in snapshot['teams'] for p in t['players']}
        snapshot['teams']=[]
        validate(config,snapshot,True)
        config['sides']['west']['players'][0]['id']='unknown'
        with self.assertRaises(ValueError):validate(config,snapshot,True)

    def test_duplicate_and_wrong_position_still_rejected(self):
        config,snapshot,_,_=fixture()
        config['sides']['west']['players'][0]['id']='102'
        with self.assertRaises(ValueError):validate(config,snapshot,True)
        config,snapshot,_,_=fixture()
        snapshot['teams'][0]['players'][0]['position']='WR'
        with self.assertRaises(ValueError):validate(config,snapshot,True)

    def test_snapshot_omits_private_fields(self):
        config,_,_,_=fixture()
        teams=[{'id':i,'name':f'Team {i}','owners':['private-id'],'roster':{'entries':[{'playerPoolEntry':{'player':{'id':i+100,'fullName':'Player','defaultPositionId':16,'proTeamId':1,'stats':[]}}}]}} for i in range(1,13)]
        result=build_snapshot(config,{'teams':teams,'members':[{'email':'private'}]})
        self.assertEqual(result['teams'][0]['players'][0]['position'],'DEF')
        self.assertNotIn('owners',result['teams'][0])
        self.assertNotIn('members',result)


if __name__=='__main__': unittest.main()

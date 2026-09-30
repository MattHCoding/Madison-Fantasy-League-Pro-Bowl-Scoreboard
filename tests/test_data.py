import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from espn import stat_points, validate
from update_scores import build_scores
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
        self.assertIsNone(result['players']['101']['liveProjection'])
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

    def test_partial_response_fails(self):
        config,snapshot,data,board=fixture()
        data['players'].pop()
        with self.assertRaises(ValueError):build_scores(config,snapshot,data,board,{})

    def test_missing_live_actual_is_unknown(self):
        config,snapshot,data,board=fixture()
        data['players'][0]['player']['stats'].pop(0)
        self.assertIsNone(build_scores(config,snapshot,data,board,{})['players']['101']['actual'])

    def test_eligibility_and_split(self):
        config,snapshot,_,_=fixture()
        config['sides']['west']['players'][0]['id']='102'
        with self.assertRaises(ValueError):validate(config,snapshot,True)
        config,snapshot,_,_=fixture()
        config['sides']['east']['teamIds'][0]=1
        with self.assertRaises(ValueError):validate(config,snapshot,True)

    def test_snapshot_omits_private_fields(self):
        config,_,_,_=fixture()
        teams=[{'id':i,'name':f'Team {i}','owners':['private-id'],'roster':{'entries':[{'playerPoolEntry':{'player':{'id':i+100,'fullName':'Player','defaultPositionId':16,'proTeamId':1,'stats':[]}}}]}} for i in range(1,13)]
        result=build_snapshot(config,{'teams':teams,'members':[{'email':'private'}]})
        self.assertEqual(result['teams'][0]['players'][0]['position'],'DEF')
        self.assertNotIn('owners',result['teams'][0])
        self.assertNotIn('members',result)


if __name__=='__main__': unittest.main()

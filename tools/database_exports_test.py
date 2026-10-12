"""Regression checks for roster joins and the imported dashboard population."""
import json
import unittest
from pathlib import Path
from database_exports import roster_players

ROOT = Path(__file__).resolve().parents[1]


class RosterIdentityTests(unittest.TestCase):
    def test_transfer_and_active_flag_duplicates_do_not_create_extra_players(self):
        rows = [dict(PlayerID='player', full_name='A Player', TeamID=team, Active=active)
                for team, active in [('one', 'true'), ('one', 'false'), ('two', 'true')]]
        players, repeats, skipped = roster_players(rows, {'player': 'portrait.webp'})
        self.assertEqual(list(players), ['player'])
        self.assertEqual(players['player']['name'], 'A Player')
        self.assertEqual(players['player']['portraitUrl'], 'portrait.webp')
        self.assertEqual(repeats, {'player': 3})
        self.assertEqual(skipped, 0)
        self.assertEqual(len(rows), 3)

    def test_blank_roster_identity_is_counted_without_inventing_a_player(self):
        players, repeats, skipped = roster_players([{'PlayerID': '', 'full_name': ''}], {})
        self.assertEqual(players, {})
        self.assertEqual(repeats, {})
        self.assertEqual(skipped, 1)

    def test_conflicting_names_cannot_silently_merge(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting player names'):
            roster_players([{'PlayerID': 'a', 'full_name': 'First Person'},
                            {'PlayerID': 'a', 'full_name': 'Second Person'}], {})

    def test_import_keeps_event_grain_and_new_source_fields(self):
        snapshot = json.loads((ROOT / 'src/data.json').read_text())
        events = snapshot['queries']['events']['rows']
        players = snapshot['queries']['players']['rows']
        self.assertEqual(len(events), 78847)
        self.assertEqual(len({row['id'] for row in events}), len(events))
        self.assertTrue(all(row['game'].startswith('2026-') for row in events))
        self.assertEqual(len({row['id'] for row in players}), len(players))
        self.assertNotIn('', {row['id'] for row in players})
        self.assertEqual(sum(row['aec'] is None for row in events), 18)
        self.assertTrue(all(row.get(key) is not None for row in events
                            for key in ('point', 'possession', 'possessionThrow', 'throwAngle', 'throwDistance')))
        self.assertEqual(snapshot['queries']['events']['source']['tables'], ['prod.throws', 'prod.games'])
        self.assertTrue(all('database-exports' in file for file in snapshot['queries']['events']['source']['files']))


if __name__ == '__main__':
    unittest.main()

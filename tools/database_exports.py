"""Read the preserved database exports without a database connection.

The manifest selects a snapshot explicitly. There is no fallback to API rows if
an imported file is missing or altered. Full exports stay local; the dashboard
receives only its selected season.
"""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

TABLES = ('throws', 'games', 'players', 'teams', 'blocks')
REQUIRED = {
    'throws': {'GameID', 'Thrower', 'Receiver', 'ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY',
               'turnover', 'DroppedThrow', 'stall', 'is_home_team', 'o_line', 'aec', 'throw_sig_id',
               'game_quarter', 'quarter_point', 'possession_num', 'possession_throw',
               'throw_angle', 'throw_distance', 'x_diff', 'y_diff'},
    'games': {'GameID', 'Year', 'HomeTeamID', 'AwayTeamID', 'Status', 'RegularSeasonWeek', 'PlayoffRound'},
    'players': {'PlayerID', 'Year', 'TeamID', 'full_name'},
    'teams': {'TeamID', 'Year', 'FullName', 'Abbrev'},
    'blocks': {'GameID', 'Defender', 'is_callahan', 'is_home_team', 'game_quarter', 'quarter_point', 'event_sig_id'},
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path, table):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        absent = REQUIRED[table] - set(reader.fieldnames or [])
        if absent:
            raise ValueError(f'{table}: missing columns {sorted(absent)}')
        for index, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'{table}: malformed CSV row {index}')
            yield row


def roster_players(rows, portraits):
    """One display identity per season player, without multiplying throw rows.

    Team/active roster rows can repeat. They are retained in the raw export;
    identity fields must agree before rows can share one display entry.
    """
    players = {}
    counts = Counter()
    skipped = 0
    for row in rows:
        pid = row['PlayerID']
        name = ' '.join(row['full_name'].split())
        if not pid:
            skipped += 1
            continue
        if not name:
            raise ValueError(f'Roster player {pid} lacks a name')
        if pid in players and players[pid]['name'] != name:
            raise ValueError(f'Conflicting player names for {pid}')
        counts[pid] += 1
        players.setdefault(pid, {'id': pid, 'name': name,
                                **({'portraitUrl': portraits[pid]} if portraits.get(pid) else {})})
    return players, {pid: count for pid, count in counts.items() if count > 1}, skipped


def load_bundle(root, portraits):
    selection = json.loads((root / 'data/database-exports/current.json').read_text())
    manifest_path = root / selection['manifest']
    manifest = json.loads(manifest_path.read_text())
    year = str(selection['season'])
    paths = {}
    for table in TABLES:
        entry = manifest['tables'][table]
        path = manifest_path.parent / entry['file']
        if sha256(path) != entry['sha256']:
            raise ValueError(f'{table}: export hash differs from the import manifest')
        paths[table] = path
    schedule = [row for row in csv_rows(paths['games'], 'games') if row['Year'] == year]
    if len({row['GameID'] for row in schedule}) != len(schedule):
        raise ValueError('Duplicate GameID in selected season')
    for row in schedule:
        for key in ('RegularSeasonWeek', 'PlayoffRound'):
            row[key] = row[key] or None
        for key in ('HomeScore', 'AwayScore'):
            row[key] = float(row[key]) if row.get(key) else None
    game_ids = {row['GameID'] for row in schedule}
    teams = [row for row in csv_rows(paths['teams'], 'teams') if row['Year'] == year]
    team_names = {row['TeamID']: (row['FullName'], row['Abbrev']) for row in teams}
    if len(team_names) != len(teams):
        raise ValueError('Duplicate TeamID in selected season')
    if any(row[side] not in team_names for row in schedule for side in ('HomeTeamID', 'AwayTeamID')):
        raise ValueError('A selected game refers to an absent team')
    roster = [row for row in csv_rows(paths['players'], 'players') if row['Year'] == year]
    players, repeated_roster, skipped = roster_players(roster, portraits)
    grouped = {gid: {'throws': [], 'blocks': []} for gid in game_ids}
    for table in ('throws', 'blocks'):
        for row in csv_rows(paths[table], table):
            gid = row['GameID']
            if gid in game_ids:
                grouped[gid][table].append(row)
            elif gid.startswith(year + '-'):
                raise ValueError(f'{table}: no game metadata for {gid}')
    # Sequence numbers are local to their game. Preserve their supplied meaning;
    # point/possession fields are not treated as league-wide identifiers.
    def order(row):
        value = row.get('global_event_seq')
        return (float(value) if value else float('inf'), row.get('throw_sig_id', ''))
    for payload in grouped.values():
        payload['throws'].sort(key=order)
    files = [{**manifest['tables'][table], 'file': str(paths[table].relative_to(root)),
              'table': f'prod.{table}'} for table in TABLES]
    audit = {'season': int(year), 'snapshot': manifest['snapshot'],
             'importedAt': manifest['importedAt'], 'repeatedRosterPlayerIds': repeated_roster,
             'rosterRows': len(roster), 'rosterRowsWithoutPlayerId': skipped,
             'uniqueRosterPlayers': len(players),
             'rosterPolicy': 'Merge repeated season player IDs only when display names agree; never join roster rows onto events.'}
    return {'schedule': schedule, 'players': players, 'payloads': grouped,
            'teamNames': team_names, 'files': files, 'audit': audit}

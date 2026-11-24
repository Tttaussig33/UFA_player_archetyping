"""Construct the audited cohort and strictly earlier-date player histories."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPORT = ROOT / 'data/database-exports/2026-10-12'
UNKNOWN = {'', 'unknown', 'null', 'none', 'nan'}
PHYSICAL = {18, 19, 20, 22, 23}
SUCCESS = {18, 19, 20}
FLAGS = {18: (0, 0, 0), 19: (0, 0, 0), 20: (1, 1, 0),
         22: (1, 0, 0), 23: (1, 0, 0), 24: (1, 0, 1)}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def eligible_throws(throws: pd.DataFrame, games: pd.DataFrame,
                    min_distance: float = 1.5) -> tuple[pd.DataFrame, dict]:
    """Retain source cp/cpoe; put all new values in research_ columns."""
    if games.GameID.duplicated().any():
        raise ValueError('Duplicate game identifiers')
    game_columns = ['GameID', 'Year', 'StartTimestamp', 'PlayoffRound']
    frame = throws.merge(games[game_columns], on='GameID', how='left',
                         validate='many_to_one', indicator=True)
    if not frame['_merge'].eq('both').all():
        raise ValueError('Throw without a matching game')
    frame = frame.loc[frame.Year.astype(str).eq('2026')].copy()
    if frame.duplicated(['GameID', 'throw_sig_id']).any():
        raise ValueError('Duplicate game/throw identifiers')
    frame['source_event_type'] = pd.to_numeric(frame.source_event_type).astype(int)
    for key in ['turnover', 'DroppedThrow', 'stall', 'cp', 'cpoe',
                'throw_distance', 'ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']:
        frame[key] = pd.to_numeric(frame[key], errors='coerce')
    for kind, rows in frame.groupby('source_event_type'):
        if kind not in FLAGS or not np.all(rows[['turnover', 'DroppedThrow', 'stall']].to_numpy() == FLAGS[kind]):
            raise ValueError(f'Unexpected event flags for type {kind}')
    xy = frame[['ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']].to_numpy()
    if not np.isfinite(xy).all():
        raise ValueError('Missing or nonfinite coordinates in 2026')
    distance = np.hypot(xy[:, 2] - xy[:, 0], xy[:, 3] - xy[:, 1])
    if not np.allclose(distance, frame.throw_distance, atol=1e-6, rtol=0):
        raise ValueError('Stored distance differs from coordinates')
    if (frame.cp.notna() & ~frame.cp.between(0, 1)).any():
        raise ValueError('Invalid nonmissing probability')
    physical = frame.source_event_type.isin(PHYSICAL)
    valid_cp = frame.cp.notna()
    summary = {'season_records': len(frame), 'physical_attempts': int(physical.sum()),
               'missing_cp_physical': int((physical & ~valid_cp).sum()),
               'all_distances_with_cp': int((physical & valid_cp).sum())}
    frame = frame.loc[physical & valid_cp & frame.throw_distance.ge(min_distance)].copy()
    frame['research_y'] = frame.source_event_type.isin(SUCCESS).astype(int)
    frame['research_date'] = pd.to_datetime(frame.StartTimestamp, errors='raise').dt.strftime('%Y-%m-%d')
    if frame.research_date.isna().any():
        raise ValueError('Missing game date')
    frame['research_player_id'] = frame.Thrower.fillna('').astype(str).str.strip()
    unknown = frame.research_player_id.str.lower().isin(UNKNOWN)
    frame.loc[unknown, 'research_player_id'] = ''
    frame['research_split'] = np.select(
        [frame.research_date.le('2026-06-14'), frame.research_date.le('2026-07-05')],
        ['fit', 'validation'], default='test')
    frame['research_huck'] = frame.throw_distance.gt(40) & (frame.ReceiverY - frame.ThrowerY).gt(30)
    frame['research_playoff'] = frame.PlayoffRound.fillna('').astype(str).ne('')
    frame = frame.drop(columns='_merge').sort_values(
        ['research_date', 'GameID', 'throw_sig_id']).reset_index(drop=True)
    summary['cohort_throws'] = len(frame)
    summary['cohort_games'] = int(frame.GameID.nunique())
    summary['known_players'] = int(frame.loc[~frame.research_player_id.eq(''), 'research_player_id'].nunique())
    summary['unknown_thrower_attempts'] = int(frame.research_player_id.eq('').sum())
    summary['splits'] = {part: {'throws': len(rows), 'games': int(rows.GameID.nunique()),
                              'first_date': rows.research_date.min(), 'last_date': rows.research_date.max()}
                         for part, rows in frame.groupby('research_split', sort=False)}
    return frame, summary


def build_history(frame: pd.DataFrame) -> pd.DataFrame:
    """No observation from the current date contributes to its own features."""
    frame = frame.copy()
    known = frame.loc[frame.research_player_id.ne('')].copy()
    known['research_original_residual'] = known.research_y - known.cp
    daily = known.groupby(['research_player_id', 'research_date'], as_index=False).agg(
        attempts=('research_y', 'size'), residual_sum=('research_original_residual', 'sum'),
        games=('GameID', 'nunique'))
    daily = daily.sort_values(['research_player_id', 'research_date'])
    grouped = daily.groupby('research_player_id', sort=False)
    for current, prior in [('attempts', 'research_prior_n'), ('residual_sum', 'research_prior_residual_sum'),
                           ('games', 'research_prior_games')]:
        daily[prior] = grouped[current].cumsum() - daily[current]
    daily['research_latest_history_date'] = grouped.research_date.shift(1)
    columns = ['research_player_id', 'research_date', 'research_prior_n',
               'research_prior_residual_sum', 'research_prior_games', 'research_latest_history_date']
    frame = frame.merge(daily[columns], on=['research_player_id', 'research_date'],
                        how='left', validate='many_to_one')
    for key in ['research_prior_n', 'research_prior_residual_sum', 'research_prior_games']:
        frame[key] = frame[key].fillna(0)
    for key in ['research_prior_n', 'research_prior_games']:
        frame[key] = frame[key].astype(int)
    has_history = frame.research_prior_n.gt(0)
    if not (frame.loc[has_history, 'research_latest_history_date'] < frame.loc[has_history, 'research_date']).all():
        raise AssertionError('History includes the current or a later date')
    if frame.loc[frame.research_player_id.eq(''), 'research_prior_n'].ne(0).any():
        raise AssertionError('Unknown players acquired shared history')
    return frame


def load_cohort() -> tuple[pd.DataFrame, dict]:
    manifest = json.loads((EXPORT / 'manifest.json').read_text())
    hashes = {}
    for table in ['throws', 'games']:
        path = EXPORT / manifest['tables'][table]['file']
        hashes[table] = sha256(path)
        if hashes[table] != manifest['tables'][table]['sha256']:
            raise ValueError(f'Export hash changed: {table}')
    games = pd.read_csv(EXPORT / 'games.csv', dtype=str, keep_default_na=False)
    usecols = ['GameID', 'throw_sig_id', 'Thrower', 'Receiver', 'source_event_type',
               'turnover', 'DroppedThrow', 'stall', 'cp', 'cpoe', 'throw_distance',
               'ThrowerX', 'ThrowerY', 'ReceiverX', 'ReceiverY']
    throws = pd.read_csv(EXPORT / 'throws.csv', usecols=usecols, dtype=str, keep_default_na=False)
    if len(throws) != manifest['tables']['throws']['rows']:
        raise ValueError('Export row count changed')
    frame, summary = eligible_throws(throws, games)
    expected = {'fit': (43791, 80), 'validation': (15737, 29), 'test': (18158, 33)}
    for part, (n, g) in expected.items():
        observed = summary['splits'][part]
        if (observed['throws'], observed['games']) != (n, g):
            raise ValueError(f'Cohort no longer matches the audit: {part}')
    frame = build_history(frame)
    summary['verified_export_sha256'] = hashes
    summary['original_cp_and_cpoe_preserved'] = True
    summary['history_uses_strictly_earlier_dates'] = True
    return frame, summary

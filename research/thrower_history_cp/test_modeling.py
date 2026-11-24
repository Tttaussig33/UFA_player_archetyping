"""Checks for outcome coding, temporal leakage, fallbacks and numerical integration."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd
from scipy.integrate import quad
from scipy.special import expit

from modeling_data import build_history, eligible_throws
from modeling_evaluation import paired_game_bootstrap
from modeling_models import (PlayerLikelihood, fit_logistic, history_feature, log_odds,
                             predict_c1, predict_c2_online)


def history_rows():
    return pd.DataFrame([
        ('a', 'g1', 'p', '2026-05-01', .8, 1, 'fit'),
        ('b', 'g1', 'p', '2026-05-01', .6, 0, 'fit'),
        ('c', 'g2', 'p', '2026-05-01', .7, 1, 'fit'),
        ('d', 'g3', 'p', '2026-05-02', .8, 1, 'validation'),
        ('e', 'g4', 'p', '2026-05-03', .7, 0, 'validation'),
        ('f', 'g1', '', '2026-05-01', .6, 1, 'fit'),
        ('g', 'g3', '', '2026-05-02', .7, 0, 'validation'),
    ], columns=['throw_sig_id', 'GameID', 'research_player_id', 'research_date', 'cp',
                'research_y', 'research_split'])


class TemporalHistoryTests(unittest.TestCase):
    def test_same_date_games_share_frozen_history(self):
        history = build_history(history_rows()).set_index('throw_sig_id')
        np.testing.assert_array_equal(history.loc[['a', 'b', 'c'], 'research_prior_n'], 0)
        self.assertEqual(history.loc['d', 'research_prior_n'], 3)
        self.assertEqual(history.loc['d', 'research_prior_games'], 2)
        self.assertAlmostEqual(history.loc['d', 'research_prior_residual_sum'], -.1)
        self.assertEqual(history.loc['e', 'research_prior_n'], 4)
        self.assertEqual(history.loc['g', 'research_prior_n'], 0)

    def test_future_outcome_changes_do_not_change_earlier_features(self):
        rows = history_rows()
        before = build_history(rows).set_index('throw_sig_id').sort_index()
        rows.loc[rows.research_date.ge('2026-05-02'), 'research_y'] = 1 - rows.loc[rows.research_date.ge('2026-05-02'), 'research_y']
        after = build_history(rows.sample(frac=1, random_state=9)).set_index('throw_sig_id').sort_index()
        columns = ['research_prior_n', 'research_prior_residual_sum', 'research_prior_games']
        pd.testing.assert_frame_equal(before.loc[['a', 'b', 'c', 'd', 'f', 'g'], columns],
                                      after.loc[['a', 'b', 'c', 'd', 'f', 'g'], columns])

    def test_no_history_k_zero_and_b_fallback(self):
        frame = build_history(history_rows())
        h = history_feature(frame, 0)
        self.assertTrue(np.isfinite(h).all())
        baseline = np.full(len(frame), .73)
        p = predict_c1(frame, np.array([2, .2, 4]), 0, baseline)
        fallback = frame.research_prior_n.eq(0)
        np.testing.assert_array_equal(p[fallback], baseline[fallback])


class OutcomeTests(unittest.TestCase):
    def test_drop_credit_missing_receiver_and_exclusions(self):
        records = []
        for i, (event, flags, cp, receiver) in enumerate([
            (18, (0, 0, 0), '.8', 'r'), (20, (1, 1, 0), '.7', ''),
            (22, (1, 0, 0), '.6', ''), (24, (1, 0, 1), '.9', ''),
            (18, (0, 0, 0), '', 'r')]):
            records.append({'GameID': 'g', 'throw_sig_id': str(i), 'Thrower': 'unknown' if i == 2 else 'p',
                            'Receiver': receiver, 'source_event_type': event, 'turnover': flags[0],
                            'DroppedThrow': flags[1], 'stall': flags[2], 'cp': cp, 'cpoe': 1 if event == 20 else .2,
                            'throw_distance': 10, 'ThrowerX': 0, 'ThrowerY': 20, 'ReceiverX': 0, 'ReceiverY': 30})
        games = pd.DataFrame([{'GameID': 'g', 'Year': '2026', 'StartTimestamp': '2026-05-01 15:00:00', 'PlayoffRound': ''}])
        frame, summary = eligible_throws(pd.DataFrame(records), games)
        np.testing.assert_array_equal(frame.research_y, [1, 1, 0])
        self.assertEqual(len(frame), 3)
        self.assertEqual(summary['missing_cp_physical'], 1)
        self.assertEqual(frame.loc[1, 'cpoe'], 1)
        self.assertEqual(frame.loc[1, 'cp'], .7)
        self.assertEqual(frame.loc[2, 'research_player_id'], '')


class NumericalModelTests(unittest.TestCase):
    def test_logistic_intercept_matches_observed_rate(self):
        beta, diagnostic = fit_logistic(np.ones((4, 1)), [1, 1, 1, 0])
        self.assertAlmostEqual(expit(beta[0]), .75, places=7)
        self.assertLess(diagnostic['max_abs_gradient'], 1e-6)

    def test_marginal_likelihood_and_gradient_against_independent_integration(self):
        frame = history_rows().loc[lambda x: x.research_player_id.ne('')].copy()
        frame.loc[frame.index[-2:], 'research_player_id'] = 'q'
        likelihood = PlayerLikelihood.from_frame(frame, 81)
        theta = np.array([.2, .9, .65])
        value, gradient = likelihood.objective(theta)
        a, b, tau = theta
        total_log_likelihood = 0
        for _, group in frame.groupby('research_player_id'):
            z, y = log_odds(group.cp), group.research_y.to_numpy()
            def integrand(u):
                eta = a + b * z + u
                log_value = np.sum(y * eta - np.logaddexp(0, eta)) - .5 * (u / tau) ** 2
                return np.exp(log_value) / (tau * np.sqrt(2 * np.pi))
            integral, _ = quad(integrand, -np.inf, np.inf, epsabs=1e-12, epsrel=1e-12)
            total_log_likelihood += np.log(integral)
        self.assertAlmostEqual(value, -total_log_likelihood / len(frame), places=10)
        finite_difference = []
        for index in range(3):
            step = np.zeros(3); step[index] = 1e-5
            finite_difference.append((likelihood.objective(theta + step)[0] - likelihood.objective(theta - step)[0]) / 2e-5)
        np.testing.assert_allclose(gradient, finite_difference, atol=1e-8, rtol=1e-6)

    def test_zero_player_variation_matches_conditional_logistic(self):
        frame = history_rows().loc[lambda x: x.research_player_id.ne('')].copy()
        likelihood = PlayerLikelihood.from_frame(frame, 41)
        value, _ = likelihood.objective([.1, 1.2, 0])
        eta = .1 + 1.2 * log_odds(frame.cp)
        direct = np.mean(np.logaddexp(0, eta) - frame.research_y.to_numpy() * eta)
        self.assertAlmostEqual(value, direct, places=12)

    def test_c2_current_and_future_outcomes_cannot_change_earlier_prediction(self):
        rows = history_rows()
        baseline = np.full(len(rows), .75)
        before = predict_c2_online(rows, [0, 1, .6], 81, baseline)
        rows.loc[rows.research_split.eq('validation'), 'research_y'] = 1 - rows.loc[rows.research_split.eq('validation'), 'research_y']
        after = predict_c2_online(rows, [0, 1, .6], 81, baseline)
        self.assertAlmostEqual(before[3], after[3], places=12)
        self.assertEqual(before[6], .75)
        self.assertEqual(after[6], .75)
        self.assertNotEqual(before[4], after[4])

    def test_c2_posterior_prediction_against_independent_integration(self):
        rows = history_rows().iloc[[0, 3]].copy().reset_index(drop=True)
        prediction = predict_c2_online(rows, [0, 1, .6], 81, np.full(2, .75))[1]
        def prior(u):
            return np.exp(-.5 * (u / .6) ** 2) / (.6 * np.sqrt(2 * np.pi))
        denominator = quad(lambda u: expit(log_odds([.8])[0] + u) * prior(u), -np.inf, np.inf)[0]
        numerator = quad(lambda u: expit(log_odds([.8])[0] + u) ** 2 * prior(u), -np.inf, np.inf)[0]
        self.assertAlmostEqual(prediction, numerator / denominator, places=9)

    def test_c2_same_date_validation_games_use_identical_prior_information(self):
        rows = history_rows().iloc[[0, 3]].copy().reset_index(drop=True)
        second_game = rows.iloc[[1]].copy()
        second_game['GameID'] = 'another_game'
        second_game['research_y'] = 0
        rows = pd.concat([rows, second_game], ignore_index=True)
        predicted = predict_c2_online(rows, [0, 1, .6], 81, np.full(3, .75))
        self.assertAlmostEqual(predicted[1], predicted[2], places=12)

    def test_paired_bootstrap_identical_models_have_zero_difference(self):
        result = paired_game_bootstrap([1, 0, 1], [.8, .4, .9], [.8, .4, .9], ['a', 'a', 'b'], 100, 7)
        for metric in result['metrics'].values():
            self.assertEqual(metric['difference'], 0)
            self.assertEqual(metric['game_bootstrap_95_interval'], [0, 0])


if __name__ == '__main__':
    unittest.main()

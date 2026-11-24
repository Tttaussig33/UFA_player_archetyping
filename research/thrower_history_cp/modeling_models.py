"""Small logistic models and a marginal-likelihood normal player model."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logsumexp, roots_hermitenorm

LOGIT_EPS = 1e-6


def log_odds(probabilities):
    p = np.clip(np.asarray(probabilities, dtype=float), LOGIT_EPS, 1 - LOGIT_EPS)
    return np.log(p) - np.log1p(-p)


def logistic_objective(beta, x, y):
    eta = x @ beta
    loss = np.mean(np.logaddexp(0, eta) - y * eta)
    grad = x.T @ (expit(eta) - y) / len(y)
    return float(loss), grad


def fit_logistic(x, y, initial=None):
    x, y = np.asarray(x, float), np.asarray(y, float)
    initial = np.zeros(x.shape[1]) if initial is None else np.asarray(initial, float)
    result = minimize(logistic_objective, initial, args=(x, y), method='BFGS', jac=True,
                      options={'gtol': 1e-9, 'maxiter': 1500})
    grad = float(np.max(np.abs(result.jac)))
    if not np.isfinite(result.fun) or grad > 1e-6:
        raise RuntimeError(f'Logistic fitting failed: {result.message}; gradient={grad}')
    return result.x, {'optimizer_success': bool(result.success), 'message': str(result.message),
                      'max_abs_gradient': grad, 'iterations': int(result.nit),
                      'fitting_mean_log_loss': float(result.fun)}


def xcp_design(frame):
    return np.column_stack([np.ones(len(frame)), log_odds(frame.cp)])


def history_feature(frame, k):
    n = frame.research_prior_n.to_numpy(float)
    denominator = n + k
    return np.divide(frame.research_prior_residual_sum.to_numpy(float), denominator,
                     out=np.zeros(len(frame)), where=denominator > 0)


def c1_design(frame, k):
    # Scaling improves numerical conditioning; c = 100 * the fitted third coefficient.
    return np.column_stack([xcp_design(frame), 100 * history_feature(frame, k)])


def predict_c1(frame, coefficients, k, b_predictions):
    p = expit(c1_design(frame, k) @ coefficients)
    fallback = frame.research_prior_n.eq(0) | frame.research_player_id.eq('')
    p[fallback.to_numpy()] = np.asarray(b_predictions)[fallback.to_numpy()]
    return p


@dataclass
class PlayerLikelihood:
    z: np.ndarray
    y: np.ndarray
    starts: np.ndarray
    nodes: np.ndarray
    log_weights: np.ndarray

    @classmethod
    def from_frame(cls, frame, order):
        known = frame.loc[frame.research_player_id.ne('')].sort_values('research_player_id')
        ids = known.research_player_id.to_numpy()
        starts = np.r_[0, np.flatnonzero(ids[1:] != ids[:-1]) + 1]
        nodes, weights = roots_hermitenorm(order)
        return cls(log_odds(known.cp), known.research_y.to_numpy(float), starts,
                   nodes, np.log(weights) - 0.5 * np.log(2 * np.pi))

    def objective(self, parameters):
        a, b, tau = parameters
        eta = a + b * self.z[:, None] + tau * self.nodes[None, :]
        ll = self.y[:, None] * eta - np.logaddexp(0, eta)
        grouped_ll = np.add.reduceat(ll, self.starts, axis=0)
        log_integrands = grouped_ll + self.log_weights
        normalizers = logsumexp(log_integrands, axis=1)
        posterior_weights = np.exp(log_integrands - normalizers[:, None])
        residual = self.y[:, None] - expit(eta)
        da = np.add.reduceat(residual, self.starts, axis=0)
        db = np.add.reduceat(residual * self.z[:, None], self.starts, axis=0)
        dt = da * self.nodes
        gradient = -np.array([np.sum(posterior_weights * d) for d in [da, db, dt]]) / len(self.y)
        return float(-normalizers.sum() / len(self.y)), gradient


def fit_c2(frame, b_coefficients, orders=(81, 161, 321), tolerance=1e-7):
    """Numerical refinement uses only the fitting likelihood, never validation scores."""
    history = []
    current = None
    for order_index, order in enumerate(orders):
        likelihood = PlayerLikelihood.from_frame(frame, order)
        initial_values = ([np.r_[b_coefficients, tau] for tau in [.1, .4, 1.0]]
                          if current is None else [current.x])
        fits = []
        for initial in initial_values:
            result = minimize(likelihood.objective, initial, method='L-BFGS-B', jac=True,
                              bounds=[(None, None), (None, None), (0, 5)],
                              options={'ftol': 1e-14, 'gtol': 1e-8, 'maxiter': 500, 'maxls': 40})
            fits.append(result)
        current = min(fits, key=lambda r: r.fun)
        grad = np.asarray(current.jac).copy()
        if current.x[2] < 1e-8 and grad[2] > 0:
            grad[2] = 0
        if not np.isfinite(current.fun) or np.max(np.abs(grad)) > 1e-5 or current.x[2] >= 4.999:
            raise RuntimeError(f'C2 did not converge away from the upper numerical bound: {current.message}')
        check_order = orders[order_index + 1] if order_index + 1 < len(orders) else order + 160
        check = PlayerLikelihood.from_frame(frame, check_order)
        check_loss, check_gradient = check.objective(current.x)
        error = abs(check_loss - current.fun)
        history.append({'order': order, 'check_order': check_order,
                        'mean_negative_log_marginal_likelihood': float(current.fun),
                        'quadrature_difference_per_throw': float(error),
                        'higher_order_max_abs_gradient': float(np.max(np.abs(check_gradient))),
                        'parameters': current.x.tolist(), 'optimizer_success': bool(current.success),
                        'message': str(current.message), 'starts': len(initial_values)})
        if error <= tolerance and np.max(np.abs(check_gradient)) <= 1e-5:
            return current.x, check_order, {'quadrature_checks': history,
                                           'known_fitting_throws': len(likelihood.y),
                                           'known_fitting_players': len(likelihood.starts)}
    raise RuntimeError('C2 quadrature did not meet the declared accuracy tolerance')


def predict_c2_online(frame, parameters, order, b_predictions, prediction_split='validation'):
    """Replay dates, predicting before updating any player with that day's results."""
    a, b, tau = parameters
    nodes, weights = roots_hermitenorm(order)
    adjustments = tau * nodes
    prior = np.log(weights) - 0.5 * np.log(2 * np.pi)
    state, counts = {}, {}
    out = np.full(len(frame), np.nan)
    b_predictions = np.asarray(b_predictions)
    # Input position is separate from arbitrary pandas index labels.
    working = frame.reset_index(drop=True)
    for _, day in working.groupby('research_date', sort=True):
        for pid, rows in day.groupby('research_player_id', sort=True):
            positions = rows.index.to_numpy()
            selected = rows.research_split.eq(prediction_split).to_numpy()
            selected_positions = positions[selected]
            if not len(selected_positions):
                continue
            if not pid or counts.get(pid, 0) == 0:
                out[selected_positions] = b_predictions[selected_positions]
            else:
                log_posterior = prior + state[pid]
                posterior = np.exp(log_posterior - logsumexp(log_posterior))
                eta = a + b * log_odds(rows.loc[rows.research_split.eq(prediction_split), 'cp'])
                out[selected_positions] = expit(eta[:, None] + adjustments[None, :]) @ posterior
        # Everyone on this date is predicted before any outcome on the date is used.
        for pid, rows in day.groupby('research_player_id', sort=True):
            if not pid:
                continue
            eta = a + b * log_odds(rows.cp)[:, None] + adjustments[None, :]
            ll = (rows.research_y.to_numpy()[:, None] * eta - np.logaddexp(0, eta)).sum(axis=0)
            updated = state.get(pid, np.zeros(order)) + ll
            state[pid] = updated - np.max(updated)
            counts[pid] = counts.get(pid, 0) + len(rows)
    return out

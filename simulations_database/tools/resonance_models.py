"""
Resonance fitting models for S-parameter data.

Provides functions to fit various resonance models to transmission (S21) and reflection (S11) data.
Currently implements Lorentzian resonance model with planned extensibility for additional models.
"""

import numpy as np
from scipy.optimize import curve_fit
from typing import Dict


def lorentzian_s21(f: np.ndarray, f0: float, eta: float, kappa: float, ampl_max: float, phi_bg: float) -> np.ndarray:
    """
    Hanger-style Lorentzian resonance model for S21 transmission with background phase.

    Physical model for transmission through a coupled resonator:
    S21(f) = ampl_max * exp(i*phi_bg) * (1 - eta * kappa / (kappa + 2j * 2 * pi * (f - f0)))

    Parameters:
        f: Frequency array (Hz)
        f0: Resonant frequency (Hz)
        eta: Coupling parameter (0 < eta < 1), represents kappa_ext/kappa_total
        kappa: Total linewidth (rad/s)
        ampl_max: Maximum transmission amplitude
        phi_bg: Background phase (radians)

    Returns:
        Complex S21 array
    """
    denominator = kappa + 2j * 2 * np.pi * (f - f0)
    return ampl_max * np.exp(1j * phi_bg) * (1 - eta * kappa / denominator)


def fit_s21_resonance(freq: np.ndarray, s21_complex: np.ndarray,
                      model: str = 'lorentzian') -> Dict:
    """
    Fit resonance model to S21 data.

    Parameters:
        freq: Frequency array (Hz)
        s21_complex: Complex S21 array
        model: Model type ('lorentzian', future: 'notch', 'reflection')

    Returns:
        Dictionary with:
            - fit_params: Fitted parameters
            - fit_errors: Parameter uncertainties
            - f_res, kappa_ext, kappa_int, Q_ext, Q_int, Q_total
            - s21_fit: Fitted S21 array
            - chi_squared: Goodness of fit
            - success: Whether fit converged
    """
    if model != 'lorentzian':
        raise NotImplementedError(f"Model '{model}' not yet implemented")

    # 1. Initial parameter guesses
    # Find resonance from minimum |S21| (notch)
    s21_mag = np.abs(s21_complex)

    # Use notch position as resonance
    min_idx = np.argmin(s21_mag)
    f0_guess = freq[min_idx]

    # Estimate linewidth from half-max points
    half_depth = (np.max(s21_mag) + np.min(s21_mag)) / 2
    above_half = s21_mag > half_depth
    half_indices = np.where(np.diff(above_half.astype(int)))[0]

    if len(half_indices) >= 2:
        linewidth_guess = freq[half_indices[-1]] - freq[half_indices[0]]
    else:
        # Fallback: 1% of frequency span
        linewidth_guess = (freq[-1] - freq[0]) * 0.01

    # kappa is in rad/s, linewidth is FWHM in Hz
    # FWHM = kappa / (2*pi), so kappa = 2*pi * FWHM
    kappa_guess = 2 * np.pi * linewidth_guess

    # eta is coupling parameter (assume ~0.5 for critical coupling)
    eta_guess = 0.5

    # ampl_max is background transmission amplitude
    # Take median of off-resonance points
    n_pts = len(freq)
    bg_indices = np.concatenate([np.arange(n_pts//5), np.arange(4*n_pts//5, n_pts)])
    ampl_max_guess = np.median(np.abs(s21_complex[bg_indices]))
    phi_bg_guess = np.median(np.angle(s21_complex[bg_indices]))

    initial_guess = [f0_guess, eta_guess, kappa_guess, ampl_max_guess, phi_bg_guess]

    # 2. Fit complex data by treating real/imag as separate observables
    s21_data_flat = np.concatenate([np.real(s21_complex), np.imag(s21_complex)])

    def model_flat(f, f0, eta, kappa, ampl_max, phi_bg):
        s21 = lorentzian_s21(f, f0, eta, kappa, ampl_max, phi_bg)
        return np.concatenate([np.real(s21), np.imag(s21)])

    # Bounds to keep parameters physical
    # f0: within frequency range, eta: 0-1, kappa: positive (1e4 allows high-Q resonators), ampl_max: 0-10, phi_bg: -pi to pi
    lower_bounds = [freq[0], 0.01, 1e4, 0.1, -np.pi]
    upper_bounds = [freq[-1], 0.9999, 1e12, 10, np.pi]

    try:
        popt, pcov = curve_fit(
            model_flat,
            freq,
            s21_data_flat,
            p0=initial_guess,
            bounds=(lower_bounds, upper_bounds),
            maxfev=10000
        )

        # Extract fitted parameters
        f0, eta, kappa, ampl_max, phi_bg = popt

        # Calculate uncertainties
        perr = np.sqrt(np.diag(pcov))

        # Calculate derived quantities from hanger model
        # kappa is in rad/s (total linewidth)
        # eta is the coupling parameter: kappa_ext / kappa_total
        kappa_ext = eta * kappa  # External coupling rate (rad/s)
        kappa_int = (1 - eta) * kappa  # Internal loss rate (rad/s)
        kappa_total = kappa  # Total linewidth (rad/s)

        # Quality factors: Q = omega0 / kappa = 2*pi*f0 / kappa
        Q_ext = 2 * np.pi * f0 / kappa_ext
        Q_int = 2 * np.pi * f0 / kappa_int
        Q_total = 2 * np.pi * f0 / kappa_total

        # Convert kappa values to Hz for consistency with old output
        kappa_ext_Hz = kappa_ext / (2 * np.pi)
        kappa_int_Hz = kappa_int / (2 * np.pi)
        kappa_total_Hz = kappa_total / (2 * np.pi)

        # Generate fitted S21
        s21_fit = lorentzian_s21(freq, *popt)

        # Chi-squared
        residual = s21_complex - s21_fit
        chi_squared = np.sum(np.abs(residual)**2) / len(freq)

        return {
            'success': True,
            'model': 'lorentzian_hanger',
            'f_res': f0,  # Keep f_res name for compatibility
            'f_res_err': perr[0],
            'eta': eta,
            'eta_err': perr[1],
            'kappa_rad_s': kappa,  # kappa in rad/s
            'kappa_err': perr[2],
            'kappa_ext': kappa_ext_Hz,  # External coupling in Hz
            'kappa_ext_err': perr[1] * kappa_total_Hz,  # Propagate eta error
            'kappa_int': kappa_int_Hz,  # Internal loss in Hz
            'kappa_int_err': perr[1] * kappa_total_Hz,
            'kappa_total': kappa_total_Hz,  # Total linewidth in Hz
            'Q_ext': Q_ext,
            'Q_int': Q_int,
            'Q_total': Q_total,
            'ampl_max': ampl_max,
            'ampl_max_err': perr[3],
            'phi_bg': phi_bg,
            'phi_bg_err': perr[4],
            's21_fit': s21_fit,
            'chi_squared': chi_squared,
            'fit_params': popt.tolist(),
            'fit_errors': perr.tolist(),
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'model': 'lorentzian'
        }

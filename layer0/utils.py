import math
from random import choices

import numpy as np
from geopy import distance
from scipy import interpolate

pb = [0.0001012910, 0.0002361887, 0.0027024326, 0.0136051939, 0.0394548393, 0.0809241217, 0.1936012148, 0.3192848214,
      0.4074064075, 0.0001507554, 0.0004206835, 0.0007118159, 0.0012199751, 0.0018869744, 0.0043439319, 0.0066332600,
      0.0100000000, 0.0192363452, 0.0297534688, 0.0523194238, 0.0650684518, 0.1032589196, 0.1317580500, 0.1617758346,
      0.2200991597, 0.2667987829, 0.3492814228, 0.3772260459, 0.4288564811, 0.4456819746, 0.4514359076, 0.4631675894,
      0.4691472686, 0.4813392240, 0.4938480176, 0.4938480176]

db = [-4.413407821, -4.636871508, -5.642458101, -6.648044693, -7.653631285, -8.659217877, -10.72625698, -13.24022346,
      -16.36871508, -4.525139665, -4.916201117, -5.083798883, -5.307262570, -5.418994413, -5.921787709, -6.201117318,
      -6.424581006, -6.927374302, -7.430167598, -7.988826816, -8.268156425, -9.106145251, -9.553072626, -10.11173184,
      -11.28491620, -12.12290503, -14.13407821, -15.08379888, -17.09497207, -18.15642458, -19.05027933, -20.05586592,
      -20.94972067, -23.35195531, -29.60893855, -35.36312849]


class BudgetLinkCalculator:
    FREQ = 868
    BW = 0.125

    def __init__(self, tx_cords, rx_cords):
        self.TX_cords = tx_cords
        self.RX_cords = rx_cords
        pass

    def calculate_snr(self, tx_pwr, fs=False):
        return np.round(self.calculate_rssi(tx_pwr, fs=fs) - self._noise_floor(), 3)

    def calculate_rssi(self, tx_pwr, fs=False):
        if fs:
            return tx_pwr + 1 - self._fs_loss() - 2.5 + 1
        return np.round(tx_pwr + 2.5 - self._hata_model() - 2.5 + 2.5, 3)

    def _hata_model(self):
        TX_alt, RX_alt = self.TX_cords[2], self.RX_cords[2]
        if RX_alt > TX_alt:
            RX_alt, TX_alt = TX_alt, RX_alt

        _distance = distance.distance(self.TX_cords[:2], self.RX_cords[:2]).km

        budget = 69.55 + 26.16 * np.log10(self.FREQ) - 13.82 * np.log10(TX_alt)
        budget += (44.9 - 6.55 * np.log10(TX_alt)) * np.log10(_distance)
        budget -= 3.2 * (np.log10(11.75 * RX_alt)) ** 2 - 4.97
        return budget

    def _fs_loss(self):
        _distance = distance.distance(self.TX_cords[:2], self.RX_cords[:2]).m
        return 20 * np.log10((4.0 * np.pi * _distance) / (299792458 / self.FREQ * 10 ** 6))

    def _noise_floor(self):
        return -173.8 + 10 * np.log10(self.BW * 10 ** 6) + 9.95


def monte_carlo(sf, snr, lenght):
    snr = snr + ((sf - 7) * 2.5)
    if snr > db[0]:
        ber = 0.0001
    elif snr < db[-1]:
        ber = 0.5
    else:
        ber = interpolate.interp1d(db, pb)(snr)
    mc = choices(population=[True, False],
                 weights=[ber, 1 - ber],
                 k=lenght * 8)

    return mc.count(True) > 1


def toa(n_size, n_sf, n_bw=125, enable_auto_ldro=True, enable_ldro=False,
        enable_eh=True, enable_crc=True, n_cr=1, n_preamble=8):
    r_sym = (n_bw * 1000.) / math.pow(2, n_sf)
    t_sym = 1000. / r_sym
    t_preamble = (n_preamble + 4.25) * t_sym

    v_DE = 0
    if enable_auto_ldro:
        if t_sym > 16:
            v_DE = 1
    elif enable_ldro:
        v_DE = 1

    v_IH = 0
    if not enable_eh:
        v_IH = 1

    v_CRC = 1
    if not enable_crc:
        v_CRC = 0

    a = 8. * n_size - 4. * n_sf + 28 + 16 * v_CRC - 20. * v_IH
    b = 4. * (n_sf - 2. * v_DE)

    n_payload = 8 + max(math.ceil(a / b) * (n_cr + 4), 0)
    t_payload = n_payload * t_sym
    t_packet = t_preamble + t_payload

    return int(round(t_packet, 0))

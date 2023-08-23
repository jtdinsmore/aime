from mcmc_core import MCMCMethod, MIN_DENSITY, MAX_DENSITY, N_FITTED_MOMENTS
import numpy as np
from scipy.special import lpmv, factorial
from scipy.linalg import pinvh
from numdifftools import Hessian

VERY_LARGE_SLOPE = 1e30
LMS = [
    # (l, m, is_real)
    (2, 2, True),
    (2, 0, True),
    (3, 3, True),
    (3, 3, False),
    (3, 2, True),
    (3, 2, False),
    (3, 1, True),
    (3, 1, False),
    (3, 0, True)]
VOLUME_SCALE = 4 / 3 * np.pi * (5/3)**(3/2)
RLM_EPSILON = 1e-20
UNCERTAINTY_RATIO = 0.25

MIN_MASS = 1e-10
SLOW_PRIOR = True

# Made for spherical lumps

# Theta long: [lump_a, lump_mass | lump_a, lump_mass, lump_pos | ..., | shell_mass, lump_pos]

# Positions and lengths are mass_weighted

MAX_LOG_PRIOR_LUMP = 2
MODEL_N = 1

def rlm(l,m,x,y,z):
    r = np.sqrt(np.maximum(RLM_EPSILON, x*x + y*y + z*z))
    return lpmv(m, l, z/r) / factorial(l + m) * r**l * np.exp(1j * m * np.arctan2(y, x))

class Lumpy(MCMCMethod):
    # Parameters are theta_short

    def set_up(self, asteroid, generate):
        self.shell_volume = np.sum(asteroid.indicator_map) * asteroid.division**3
        self.surface_am = asteroid.surface_am
        self.X, self.Y, self.Z = np.meshgrid(asteroid.grid_line, asteroid.grid_line, asteroid.grid_line)
        if SLOW_PRIOR:
            self.indicator = asteroid.indicator_map

        # moment_field = asteroid.moment_field(asteroid.surface_am)
        # bulk_am_sqr = np.sum(moment_field[-1] * asteroid.indicator_map) * asteroid.division**3
        # complex_klms = np.einsum("iabc,abc->i", moment_field[:-1,:,:,:], asteroid.indicator_map) * asteroid.division**3
        # self.shell_com = np.array([
        #     -complex_klms[3].real * 2,
        #     -complex_klms[3].imag * 2,
        #     complex_klms[2].real
        # ]) / asteroid.surface_am / self.shell_volume
        # complex_klms /= bulk_am_sqr

        if asteroid.true_moments is None:
            raise Exception("The moments of the shape, as computed with very fine precision, must be passed in explicitly for the lumpy method")


        complex_klms = asteroid.true_moments
        self.shell_com = np.array([
            -complex_klms[3].real * 2,
            -complex_klms[3].imag * 2,
            complex_klms[2].real
        ]) * asteroid.surface_am
        self.shell_free_klms = np.array([
            complex_klms[4].real,
            complex_klms[6].real,
            complex_klms[15].real,
            complex_klms[15].imag,
            complex_klms[14].real,
            complex_klms[14].imag,
            complex_klms[13].real,
            complex_klms[13].imag,
            complex_klms[12].real,
        ])
        
        assert(MODEL_N >= 1) # Must have at least one lump
        assert(MODEL_N <= MAX_LOG_PRIOR_LUMP) # Log prior can only handle so many


    def short_name(self):
        return "lumpy"

    def get_theta_long(self, theta_short):
        mass_sum = theta_short[1]
        for i in range(MODEL_N - 1):
            mass_sum += theta_short[3 + 5 * i]
        
        shell_mass = self.shell_volume - mass_sum
        pos_sum = self.shell_com * shell_mass
        for i in range(MODEL_N - 1):
            pos_sum += theta_short[(4 + i * 5):(7 + i * 5)]
        return np.append(theta_short, np.append([shell_mass], -pos_sum))

    def pick_parameters(self, local_rng):
        success = False
        while not success:
            mass = (local_rng.random() - 0.5) * self.shell_volume
            params = np.array([
                local_rng.random() * self.surface_am / 2 * mass,
                mass
            ])
            for i in range(MODEL_N - 1):
                mass = (local_rng.random() - 0.5) * self.shell_volume
                params = np.append(params, [
                    local_rng.random() * self.surface_am / 2 * mass,
                    mass,
                    (local_rng.random() - 0.5) * 2 * self.surface_am * mass,
                    (local_rng.random() - 0.5) * 2 * self.surface_am * mass,
                    (local_rng.random() - 0.5) * 2 * self.surface_am * mass
                ])
            if self.log_prior(self.get_theta_long(params)) > -1:
                success = True
        return params

    def log_prior(self, theta_long):
        # What are the pairs that are overlapping?
        shell_density = theta_long[-4] / self.shell_volume
        lump_densities = [theta_long[1]**4 / theta_long[0]**3 / VOLUME_SCALE]
        for i in range(0, MODEL_N - 1):
            lump_densities.append(theta_long[3 + i * 5]**4 / theta_long[2 + i * 5]**3 / VOLUME_SCALE)

        # Prior on a_m
        am_limit = 0
        for i in range(MODEL_N):
            lump_mass = theta_long[1] if i == 0 else theta_long[-2 + 5 * i]
            length = (theta_long[0] if i == 0 else theta_long[-3 + 5 * i]) / lump_mass
            if length < MIN_MASS:
                am_limit += (length - MIN_MASS) * VERY_LARGE_SLOPE / MIN_MASS
            if length > 2 * self.surface_am:
                am_limit += (2 * self.surface_am - length) * VERY_LARGE_SLOPE
        if am_limit:
            return am_limit

        # Prior on mass
        for i in range(MODEL_N):
            lump_mass = theta_long[1] if i == 0 else theta_long[-2 + 5 * i]
            if abs(lump_mass) < MIN_MASS:
                return (abs(lump_mass) - MIN_MASS) / MIN_MASS * VERY_LARGE_SLOPE
            
        intersections = []

        # No lumps
        intersections.append(shell_density)

        # Single lumps
        for density in lump_densities:
            intersections.append(density + shell_density)

        # Double lumps
        lump_poses = [theta_long[-3:] / theta_long[1]]
        for i in range(MODEL_N - 1):
            lump_poses.append(theta_long[(4 + i * 5):(7 + i * 5)] / theta_long[3 + 5 * i])
        for i, pos_i in enumerate(lump_poses):
            lump_mass_i = theta_long[1] if i == 0 else theta_long[-2 + 5 * i]
            radius_i = (theta_long[0] if i == 0 else theta_long[-3 + 5 * i]) * np.sqrt(5 / 3) / lump_mass_i
            for j, pos_j in enumerate(lump_poses[:i]):
                lump_mass_j = theta_long[1] if j == 0 else theta_long[-2 + 5 * j]
                radius_j = (theta_long[0] if j == 0 else theta_long[-3 + 5 * j]) * np.sqrt(5 / 3) / lump_mass_j
                dist_sqr = np.sum((pos_i - pos_j)**2)
                if dist_sqr < (radius_i + radius_j)**2:
                    intersections.append(lump_densities[i] + lump_densities[j] + shell_density)

        if SLOW_PRIOR:
            overage = 0
            for i in range(MODEL_N):
                lump_mass = theta_long[1] if i == 0 else theta_long[-2 + 5 * i]
                lump_pos = (theta_long[-3:] if i == 0 else theta_long[(-1 + i * 5):(2 + i * 5)]) / lump_mass
                lump_radius_sqr = (theta_long[0] if i == 0 else theta_long[-3 + 5 * i])**2 * 5 / 3 / lump_mass**2
                interior = (self.X - lump_pos[0])**2 + (self.Y - lump_pos[1])**2 + (self.Z - lump_pos[2])**2 <= lump_radius_sqr
                disallowed = np.sum(~self.indicator & interior)
                if disallowed > 0:
                    overage += disallowed * (1 + np.sum(lump_pos * lump_pos) / self.surface_am**2 + lump_radius_sqr / self.surface_am**2)
            if overage > 0:
                return -overage * VERY_LARGE_SLOPE

        return min(0, np.min(intersections) - MIN_DENSITY) * VERY_LARGE_SLOPE + \
            min(0, MAX_DENSITY - np.max(intersections)) * VERY_LARGE_SLOPE

    def get_klms(self, theta_long):
        denom = self.surface_am ** 2 * theta_long[-4] # Shell moi
        denom += (theta_long[0]**2 + theta_long[-1]**2 + theta_long[-2]**2 + theta_long[-3]**2) / theta_long[1]# Lump 1 moi
        for i in range(MODEL_N - 1):
            denom += (theta_long[5 * i + 2]**2 + theta_long[5 * i + 4]**2 + theta_long[5 * i + 5]**2 + theta_long[5 * i + 6]**2) / theta_long[5 * i + 3]
        # Surface
        klms = theta_long[-4] * self.shell_free_klms
        # Lumps
        for i in range(MODEL_N):
            lump_mass = theta_long[1] if i == 0 else theta_long[-2 + 5 * i]
            lump_pos = (theta_long[-3:] if i == 0 else theta_long[(-1 + i * 5):(2 + i * 5)]) / lump_mass
            for j, (l, m, is_real) in enumerate(LMS):
                rlm_val = rlm(l, m, lump_pos[0], lump_pos[1], lump_pos[2])
                klms[j] += lump_mass / self.surface_am**l * (rlm_val.real if is_real else rlm_val.imag)

        return klms / denom * self.surface_am**2

    def get_map(self, theta_long, unc, asteroid):
        densities = np.ones_like(asteroid.indicator_map) * theta_long[-4] / self.shell_volume

        for i in range(MODEL_N):
            lump_mass = theta_long[1] if i == 0 else theta_long[-2 + 5 * i]
            lump_pos = (theta_long[-3:] if i == 0 else theta_long[(-1 + i * 5):(2 + i * 5)]) / lump_mass
            lump_length = (theta_long[0] if i == 0 else theta_long[-3 + 5 * i]) / lump_mass
            lump_density = lump_mass / lump_length**3 / VOLUME_SCALE
            densities[(self.X - lump_pos[0]) ** 2 + (self.Y - lump_pos[1]) ** 2 + (self.Z - lump_pos[2]) ** 2 < (lump_length**2 * 5 / 3)] += lump_density

        densities[~asteroid.indicator_map] = np.nan
        densities /= np.nansum(densities)
        if unc is None:
            return densities
        else:
            return densities, np.ones_like(densities)

    def scatter_walkers(self, theta_start, n_walkers, data_storage):
        if MODEL_N == 1:
            pos = np.zeros((n_walkers, self.n_free))
            for i in range(self.n_free):
                pos[:,i] = np.random.randn(n_walkers) * UNCERTAINTY_RATIO * theta_start[i] + theta_start[i]
            return pos

        else:
            inv_hess = pinvh(Hessian(lambda theta: -self.hess_like(theta, data_storage))(theta_start))
            evals, evecs = np.linalg.eigh(inv_hess)
            print(evals)
            sigmas = np.sqrt(np.maximum(1e5, evals))

            poses = []
            for _ in range(n_walkers):
                direction = np.random.randn(7)
                direction /= np.sqrt(np.sum(direction**2))
                poses.append(theta_start + 2 * sigmas * direction @ evecs.transpose())
            return np.array(poses)

    def hess_like(self, theta_short, data_storage):
        theta_long = self.get_theta_long(theta_short)
        free_klms = self.get_klms(theta_long)[:N_FITTED_MOMENTS]
        diff_klms = free_klms - data_storage.data # Only need the unconstrained ones
        return -0.5 * diff_klms.transpose() @ data_storage.data_inv_covs @ diff_klms
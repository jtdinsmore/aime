import numpy as np
import quaternion
from math import factorial

DATA_WIDTH = 500
EARTH_RADIUS = 6_370_000
x = np.linspace(0, 12 * np.pi, DATA_WIDTH)

def simulate(cadence, jlms, theta, radius, spinx, spiny, spinz, impact_parameter,
    speed, mu, central_radius, drc=-1, enforce_drc=False, vel_mul=1):

    consider_x = x[:int(DATA_WIDTH / 2 * (1 + drc / 10)) - 1] if enforce_drc else x

    y1 = np.zeros_like(consider_x)
    y2 = np.zeros_like(consider_x)
    y3 = np.zeros_like(consider_x)
    y4 = np.zeros_like(consider_x)
    for n, p in enumerate(theta):
        mul = 1
        if n >= 3:
            mul = 0.000001
        y1 += abs(mul * p**3 * np.sin(consider_x * n))
        y2 += mul * p**3 * np.cos(consider_x * n)
        y3 += mul * p**3 * np.cos(consider_x * (n+1))
        y4 += mul * p**3 * np.sin(consider_x * (n+1))
    
    res = np.append(np.append(np.append(y1, y2), y3), y4).reshape(4, -1)
    res /= np.linalg.norm(res, axis=0)

    return res.reshape(-1)

if __name__ == "__main__":
    import time
    start = time.time()
    simulate(120, [1.0], [0.39269908169, 0, -0.09766608], 1000, 0.00024682682, 0, -0.00024682682, 0.39269908169, 31850000, 4000, 3.986004418e14, 6370000)
    print(f"Test time: {time.time() - start} s")

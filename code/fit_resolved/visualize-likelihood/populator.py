import time, sys, os, inspect
from multiprocessing import Pool

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

import numpy as np
import matplotlib.pyplot as plt
import asteroids_0_2 as asteroids
from random_vector import *


ASTEROIDS_MAX_K = 2 # Remember to change the counterpart in backend.hpp
ASTEROIDS_MAX_J = 0 # Remember to change the counterpart in backend.hpp
EARTH_RADIUS = 6370000
GM = 3.986004418e14

THETA_X_INDEX = 0
THETA_Y_INDEX = 1
PLOT_SIZE = 100

DISTANCE_RATIO_CUT = 2

if len(sys.argv) not in [2, 3]:
    raise Exception("Please pass a file to describe the fit")
output_name = sys.argv[1]
f = open("../../../staged/" + output_name+".txt", 'r')
f.readline()
cadence = int(f.readline())
impact_parameter = EARTH_RADIUS * int(f.readline())
radius = float(f.readline())
speed = float(f.readline())
spin = [float(x) for x in f.readline().split(',')]
jlms = [float(x) for x in f.readline().split(',')]
theta_true = [float(x) for x in f.readline().split(',')]
theta_high = np.asarray([float(x) for x in f.readline().split(',')])
theta_low = np.asarray([float(x) for x in f.readline().split(',')])

sigma = float(f.readline())
while output_name[-1] == '\n':
    output_name = output_name[:-1]
f.close()
assert(len(theta_true) == len(theta_high) == len(theta_low))
assert(len(theta_true) == (ASTEROIDS_MAX_K + 1)**2 - 6)
assert(len(jlms) == (ASTEROIDS_MAX_J + 1)**2)
assert(np.all(theta_high > theta_low))

print("Cadence {}, impact parameter {}, speed {}".format(cadence, impact_parameter, speed))
print("Spin", spin)
print("Jlms", jlms)
print("Theta true", theta_true)
print("Theta high", theta_high)
print("Theta low", theta_low)
print("Sigma", sigma)
print("Name", output_name)
N_DIM = len(theta_true)

def fit_function(theta, target_length=None):
    resolved_data = asteroids.simulate(cadence, jlms, theta[1:], radius,
        spin[0], spin[1], spin[2], theta[0], impact_parameter, speed, GM, EARTH_RADIUS, DISTANCE_RATIO_CUT, True)
    if target_length is not None:
        while len(resolved_data)//3 < target_length:
            resolved_data.append(resolved_data[-3])
            resolved_data.append(resolved_data[-3])
            resolved_data.append(resolved_data[-3])
    return np.asarray(resolved_data).reshape(-1, 3)

def red_chi(theta, y, yerr):
    # Normal likelihood
    try:
        model = fit_function(theta, len(y))
    except RuntimeError:
        return np.inf # Zero likelihood

    chisq = 0
    for i in range(len(y)):
        chisq += np.matmul(y[i] - model[i], np.matmul(yerr[i], y[i] - model[i]))
    return chisq / len(y) / 3


start = time.time()
y = fit_function(theta_true)
print("Data generation took {} s".format(time.time() - start))
y, yerr = randomize_rotate_uniform(y, sigma)

plt.figure(figsize=(12, 4))
x_display = np.arange(len(y))
plt.fill_between(x_display, y[:,0]+yerr[:,0,0]**(-0.5), y[:,0]-yerr[:,0,0]**(-0.5), alpha=0.5)
plt.fill_between(x_display, y[:,1]+yerr[:,1,1]**(-0.5), y[:,1]-yerr[:,1,1]**(-0.5),alpha=0.5)
plt.fill_between(x_display, y[:,2]+yerr[:,2,2]**(-0.5), y[:,2]-yerr[:,2,2]**(-0.5),  alpha=0.5)
plt.plot(x_display, y[:,0], label='x')
plt.plot(x_display, y[:,1], label='y')
plt.plot(x_display, y[:,2], label='z')
plt.xlabel("Time (Cadences)")
plt.ylabel("Spin (rad/s)")
plt.legend()
plt.show()

print("Unit red chi:", red_chi(theta_true, y, yerr))


red_chis = []

xs = np.linspace(theta_low[THETA_X_INDEX], theta_high[THETA_X_INDEX], PLOT_SIZE)
ys = np.linspace(theta_low[THETA_Y_INDEX], theta_high[THETA_Y_INDEX], PLOT_SIZE)

def gen_line(theta_y):
    line = []
    for theta_x in xs:
        theta = [0] * len(theta_true)
        for i, t in enumerate(theta_true):
            if i == THETA_X_INDEX:
                theta[i] = theta_x
            elif i == THETA_Y_INDEX:
                theta[i] = theta_y
            else:
                theta[i] = t
        line.append(red_chi(theta, y, yerr))
    return line

with Pool(6) as pool:
    red_chis = pool.map(gen_line, ys)

f = open("redchi-{}-{}{}-cut.dat".format(THETA_X_INDEX, THETA_Y_INDEX, "" if DISTANCE_RATIO_CUT > 0 else "-no"), 'w')
f.write("{}, {}\n".format(THETA_X_INDEX, THETA_Y_INDEX))
f.write(", ".join([str(t) for t in theta_true]) + "\n")
f.write(", ".join([str(t) for t in xs]) + "\n")
f.write(", ".join([str(t) for t in ys]) + "\n")
for l in red_chis:
    f.write(", ".join([str(c) for c in l]) + "\n")
f.close()

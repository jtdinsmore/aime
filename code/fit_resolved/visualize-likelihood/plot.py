import numpy as np
import matplotlib.pyplot as plt
import os

plt.style.use("jcap")

for file in os.listdir():
    if file[-4:] != ".dat":
        continue
    f = open(file, 'r')
    lines = f.readlines()
    f.close()
    index_x, index_y = lines[0].split(', ')
    index_x = int(index_x)
    index_y = int(index_y)

    theta_true = []
    for t in lines[1].split(', '):
        theta_true.append(float(t))

    xs = []
    for x in lines[2].split(', '):
        xs.append(float(x))

    ys = []
    for y in lines[3].split(', '):
        ys.append(float(y))

    red_chis = []
    for line in lines[4:]:
        red_line = []
        for rc in line.split(', '):
            red_line.append(np.log10(float(rc)))
        red_chis.append(red_line)

    finites = np.asarray(red_chis).reshape(len(red_chis) * len(red_chis[1]))
    finites = finites[np.isfinite(finites)]

    plt.figure()
    c = plt.pcolor(xs, ys, red_chis, vmax=np.nanpercentile(finites, 80), vmin=np.nanpercentile(finites, 1))
    cax = plt.colorbar(c)
    cax.set_label("$\log_{10}\mathcal{\chi}^2$")
    plt.xlabel("$\\theta_{{{}}}$".format(index_x+1))
    plt.ylabel("$\\theta_{{{}}}$".format(index_y+1))
    plt.scatter([theta_true[index_x]], [theta_true[index_y]], marker='*', color='C1')
    plt.tight_layout()
    plt.savefig(file[:-4]+".png")
plt.show()

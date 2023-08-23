import numpy as np
import scipy.linalg, corner
import matplotlib.pyplot as plt
from mpmath import mp
from matplotlib.lines import Line2D

TILT_UNIFORM_TRUE = 0
TILT_UNIFORM_GAUSS = 1
UNCORR_SCALE = 2
EPSILON = 1e-10

def randomize(model, y, sigma):
    if model == TILT_UNIFORM_TRUE:
        return randomize_rotate_uniform(y, sigma)
    elif model == TILT_UNIFORM_GAUSS:
        return randomize_rotate_gauss(y, sigma)
    elif model == UNCORR_SCALE:
        return randomize_uncorr_scale(y, sigma)
    else:
        raise Exception(f"Model {model} not implemented")

def log_likelihood(model, y, true, length, sigma):
    if model == TILT_UNIFORM_TRUE:
        return like_rotate_uniform(y, true, length, sigma)
    elif model == TILT_UNIFORM_GAUSS or model == UNCORR_SCALE:
        return  like_cov(y, true, length, sigma)
    else:
        raise Exception(f"Model {model} not implemented")


def like_rotate_uniform(y, model, length, sigma):
    sigma_theta, ratio = sigma
    trimmed_y = y[:length]
    trimmed_model = model[:length]
    rhos = scipy.linalg.norm(trimmed_y, axis=1) / scipy.linalg.norm(trimmed_model, axis=1)
    thetas = np.arccos(0.999999999*np.sum(trimmed_y * trimmed_model, axis=1) / np.sum(trimmed_y**2, axis=1) * rhos)
    prob_theta = -0.5 * thetas**2 / sigma_theta**2
    prob_rho = -0.5 * np.log(rhos)**2 / (ratio * sigma_theta)**2 - np.log(rhos)
    return np.sum(prob_theta + prob_rho)

def like_cov(y, model, length, y_inv_covs):
    log_like = 0
    for i in range(length):
        log_like += np.sum((y[i] - model[i]) * np.matmul(y_inv_covs[i], y[i] - model[i]))
    return -0.5 * log_like



def vadd(a, b):
    return [a[i] + b[i] for i in range(len(a))]
def vmul(a, b):
    return [ai * b for ai in a]
def vcross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]]
def vdot(a, b):
    return np.sum([a[i] * b[i] for i in range(len(a))])
def vnorm(a):
    return np.sqrt(np.sum([ai * ai for ai in a]))

# Make an un_uniform randomizer
def randomize_rotate_uniform_err(spin, sigma):
    sigma_theta, ratio = sigma
    norm2 = spin[0]**2 + spin[1]**2 + spin[2]**2

    return 0.5 * np.exp(sigma_theta**2 * (-1+ 2 * ratio**2)) * (
        (np.exp(-sigma_theta**2) - 2 * np.exp(-sigma_theta**2 * ratio**2) + np.cosh(sigma_theta**2)) * np.array([
        [spin[0]**2, spin[0] * spin[1], spin[0] * spin[2]],
        [spin[0] * spin[1], spin[1]**2, spin[1] * spin[2]],
        [spin[0] * spin[2], spin[1] * spin[2], spin[2]**2]])
        + np.sinh(sigma_theta**2) * norm2 * np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    )

# Do the sophisticated, turning error
def randomize_rotate_uniform(data, sigma):
    newy = []
    ycovs = []
    sigma_theta, ratio = sigma

    for x, y, z in data:
        norm = np.sqrt(x**2 + y**2 + z**2)
        new_norm = norm * np.random.lognormal(sigma=sigma_theta * ratio)
        theta = np.arccos(z / norm)
        phi = np.arctan2(y, x)
        rot_mat = np.matmul(
            np.array([[np.cos(-theta), 0, np.sin(-theta)], [0, 1, 0], [-np.sin(-theta), 0, np.cos(-theta)]]),
            np.array([[np.cos(-phi), -np.sin(-phi), 0], [np.sin(-phi), np.cos(-phi), 0], [0, 0, 1]])
        )
        tilt_phi = np.random.random() * np.pi
        tilt_theta = np.random.randn() * sigma_theta
        untilt_vec = [np.sin(tilt_theta) * np.cos(tilt_phi), np.sin(tilt_theta) * np.sin(tilt_phi), np.cos(tilt_theta)]
        newvec = np.matmul(rot_mat.transpose(), untilt_vec) * new_norm
        covs = randomize_rotate_uniform_err(newvec, sigma)
        newy.append(newvec)
        ycovs.append(scipy.linalg.pinvh(covs))

    return np.array(newy), np.array(ycovs)

def randomize_rotate_gauss(data, sigma):
    newy = []
    ycovs = []
    for x, y, z in data:
        cov = randomize_rotate_uniform_err([x, y, z], sigma)
        evals, evecs = scipy.linalg.eigh(cov)
        spacing = np.sqrt(np.abs(evals))
        newvec = np.array([x, y, z]) + np.matmul(evecs, spacing * np.random.randn(3))
        newy.append(newvec)
        ycovs.append(scipy.linalg.pinvh(randomize_rotate_uniform_err(newvec, sigma)))
    return np.array(newy), np.array(ycovs)


def randomize_uncorr_scale(data, sigma):
    newy = []
    ycovs = []
    for x, y, z in data:
        norm = np.sqrt(x**2 + y**2 + z**2)
        newvec = np.array([x, y, z]) + np.randn(3) * sigma * norm
        newy.append(newvec)
        ycovs.append(scipy.linalg.pinvh(np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]) * sigma**2 * norm**2))
    return np.array(newy), np.array(ycovs)


if __name__ == "__main__":

    plt.style.use("jcap")

    count = 100_000
    spin = np.array([[0.00006464182, 0.00012928364, -0.00012928364]]*count) * 3600
    sigma = 0.01, 0
    newspin, err = randomize_rotate_uniform(spin, sigma)
    fig = corner.corner(newspin, labels=['$\omega_x$ (rad / hr)', '$\omega_y$ (rad / hr)', '$\omega_z$ (rad / hr)'], color="C0")
    
    gauss_spin, err = randomize_rotate_gauss(spin, sigma)
    corner.corner(gauss_spin, fig=fig, labels=['$\omega_x$ (rad / hr)', '$\omega_y$ (rad / hr)', '$\omega_z$ (rad / hr)'], color="C1")

    custom_lines = [Line2D([0], [0], color="C0", lw=2),
                    Line2D([0], [0], color="C1", lw=2)]
    fig.legend(custom_lines, ['True', 'Gaussian'])

    plt.savefig("random-figs/random-vector-unc.pdf")
    plt.savefig("random-figs/random-vector-unc.png")

    plt.figure()
    true_norms = np.linalg.norm(newspin, axis=1)
    gauss_norms = np.linalg.norm(gauss_spin, axis=1)
    bins=np.linspace(np.min(gauss_norms), np.max(gauss_norms), 20)
    plt.hist(true_norms, bins=bins, color="C0", density=True, histtype="step", fill=False, label="True")
    plt.hist(gauss_norms, bins=bins, color="C1", density=True, histtype="step", fill=False, label="Gaussian")
    plt.xlabel("$\omega$ (rad / hr)")
    plt.ylabel("PDF (hr / rad)")
    plt.legend()
    plt.tight_layout()
    plt.savefig("random-figs/random-vector-norm.pdf")
    plt.savefig("random-figs/random-vector-norm.png")
    plt.show()

    err_vec = (np.sum(err[0]**2, axis=0))**(1/4)
    cov = np.cov(np.transpose(newspin))
    err = scipy.linalg.pinvh(err[0])
import pylab as plt
import jax.numpy as jnp
from scipy.stats.kde import gaussian_kde
from jaxns.utils import safe_gaussian_kde, tuple_prod, resample, cumulative_logsumexp
from jax import random
from matplotlib.animation import FuncAnimation


def plot_diagnostics(results, save_name=None):
    fig, axs = plt.subplots(5, 1, sharex=True, figsize=(8, 10))
    log_X = results.log_X[:results.num_samples]
    axs[0].plot(-log_X, results.n_per_sample[:results.num_samples])
    axs[0].set_ylabel(r'$n(X)$')
    #detect if too small log likelihood
    log_likelihood = results.log_L_samples[:results.num_samples]
    max_log_likelihood = jnp.max(log_likelihood)
    likelihood = jnp.exp(log_likelihood - max_log_likelihood)
    axs[1].plot(-log_X, likelihood)
    axs[1].hlines(1., jnp.min(-log_X),
                  jnp.max(-log_X), colors='black', ls='dashed',
                  label=r"$\log L_{{\rm max}}={:.1f}$".format(max_log_likelihood))
    axs[1].set_ylabel(r'$L(X)/L_{\rm max}$')
    axs[1].legend()
    axs[2].plot(-log_X, jnp.exp(results.log_p[:results.num_samples]))
    axs[2].vlines(-results.H, 0., jnp.exp(jnp.max(results.log_p[:results.num_samples])), colors='black', ls='dashed', label='-logX=-H={:.1f}'.format(-results.H))
    axs[2].set_ylabel(r'$Z^{-1}L(X) dX$')
    axs[2].legend()
    log_cum_evidence = cumulative_logsumexp(results.log_p[:results.num_samples])
    cum_evidence = jnp.exp(log_cum_evidence)
    axs[3].plot(-log_X, cum_evidence)
    axs[3].hlines(1., jnp.min(-log_X),
                  jnp.max(-log_X), colors='black', ls='dashed',
                  label=r"$\log Z={:.1f}$".format(results.logZ))
    axs[3].set_ylabel(r'$Z(x > X)/Z$')
    axs[3].legend()
    axs[4].plot(-log_X, results.sampler_efficiency[:results.num_samples])
    axs[4].hlines(results.efficiency, jnp.min(-log_X),
                  jnp.max(-log_X), colors='black', ls='dashed',
                  label='avg. eff.={:.3f}'.format(results.efficiency))
    axs[4].set_ylabel("sampler efficiency")
    axs[4].set_xlabel(r'$-\log X$')
    axs[4].set_ylim(0., 1.05)
    axs[4].legend()
    if save_name is not None:
        fig.savefig(save_name)
    plt.show()


def plot_cornerplot(results, vars=None, save_name=None):
    rkey0 = random.PRNGKey(123496)
    vars = _get_vars(results, vars)
    ndims = _get_ndims(results, vars)
    figsize = min(20, max(4, int(2 * ndims)))
    fig, axs = plt.subplots(ndims, ndims, figsize=(figsize, figsize))
    if ndims == 1:
        axs = [[axs]]
    nsamples = results.num_samples
    log_p = results.log_p[:results.num_samples]
    nbins = int(jnp.sqrt(results.ESS)) + 1
    lims = {}
    dim = 0
    for key in vars:  # sorted(results.samples.keys()):
        n1 = tuple_prod(results.samples[key].shape[1:])
        for i in range(n1):
            samples1 = results.samples[key][:results.num_samples,...].reshape((nsamples, -1))[:, i]
            if jnp.std(samples1) == 0.:
                dim += 1
                continue
            weights = jnp.where(jnp.isfinite(samples1), jnp.exp(log_p), 0.)
            log_weights = jnp.where(jnp.isfinite(samples1), log_p, -jnp.inf)
            samples1 = jnp.where(jnp.isfinite(samples1), samples1, 0.)
            # kde1 = gaussian_kde(samples1, weights=weights, bw_method='silverman')
            # samples1_resampled = kde1.resample(size=int(results.ESS))
            rkey0, rkey = random.split(rkey0, 2)
            samples1_resampled = resample(rkey, samples1, log_weights, S=int(results.ESS))
            binsx = jnp.linspace(*jnp.percentile(samples1_resampled, [0, 100]), 2 * nbins)
            dim2 = 0
            for key2 in vars:  # sorted(results.samples.keys()):
                n2 = tuple_prod(results.samples[key2].shape[1:])
                for i2 in range(n2):
                    ax = axs[dim][dim2]
                    if dim2 > dim:
                        dim2 += 1
                        ax.set_xticks([])
                        ax.set_xticklabels([])
                        ax.set_yticks([])
                        ax.set_yticklabels([])
                        continue
                    if n2 > 1:
                        title2 = "{}[{}]".format(key2, i2)
                    else:
                        title2 = "{}".format(key2)
                    if n1 > 1:
                        title1 = "{}[{}]".format(key, i)
                    else:
                        title1 = "{}".format(key)
                    ax.set_title('{} {}'.format(title1, title2))
                    if dim == dim2:
                        # ax.plot(binsx, kde1(binsx))
                        ax.hist(samples1_resampled, bins='auto', fc='None', edgecolor='black', density=True)
                        sample_mean = jnp.average(samples1, weights=weights)
                        sample_std = jnp.sqrt(jnp.average((samples1 - sample_mean) ** 2, weights=weights))
                        ax.set_title("{:.2f}:{:.2f}:{:.2f}\n{:.2f}+-{:.2f}".format(
                            *jnp.percentile(samples1_resampled, [5, 50, 95]), sample_mean, sample_std))
                        ax.vlines(sample_mean, *ax.get_ylim(), linestyles='solid', colors='red')
                        ax.vlines([sample_mean - sample_std, sample_mean + sample_std],
                                  *ax.get_ylim(), linestyles='dotted', colors='red')
                        ax.set_xlim(binsx.min(), binsx.max())
                        lims[dim] = ax.get_xlim()
                    else:
                        samples2 = results.samples[key2][:results.num_samples,...].reshape((nsamples, -1))[:, i2]
                        if jnp.std(samples2) == 0.:
                            dim2 += 1
                            continue
                        weights = jnp.where(jnp.isfinite(samples2), jnp.exp(log_p), 0.)
                        log_weights = jnp.where(jnp.isfinite(samples2), log_p, -jnp.inf)
                        samples2 = jnp.where(jnp.isfinite(samples2), samples2, 0.)
                        # kde2 = gaussian_kde(jnp.stack([samples1, samples2], axis=0),
                        #                     weights=weights,
                        #                     bw_method='silverman')
                        # samples2_resampled = kde2.resample(size=int(results.ESS))
                        rkey0, rkey = random.split(rkey0, 2)
                        samples2_resampled = resample(rkey, jnp.stack([samples1,samples2], axis=-1), log_weights, S=int(results.ESS))
                        # norm = plt.Normalize(log_weights.min(), log_weights.max())
                        # color = jnp.atleast_2d(plt.cm.jet(norm(log_weights)))
                        ax.hist2d(samples2_resampled[:, 1], samples2_resampled[:,0],bins=(nbins, nbins), density=True, cmap=plt.cm.bone_r)
                        # ax.scatter(samples2_resampled[:, 1], samples2_resampled[:, 0], marker='+', c='black', alpha=0.5)
                        # binsy = jnp.linspace(*jnp.percentile(samples2_resampled[:, 1], [0, 100]), 2 * nbins)
                        # X, Y = jnp.meshgrid(binsx, binsy, indexing='ij')
                        # ax.contour(kde2(jnp.stack([X.flatten(), Y.flatten()], axis=0)).reshape((2 * nbins, 2 * nbins)),
                        #            extent=(binsy.min(), binsy.max(),
                        #                    binsx.min(), binsx.max()),
                        #            origin='lower')
                    if dim == ndims - 1:
                        ax.set_xlabel("{}".format(title2))
                    if dim2 == 0:
                        ax.set_ylabel("{}".format(title1))

                    dim2 += 1
            dim += 1
    for dim in range(ndims):
        for dim2 in range(ndims):
            if dim == dim2:
                continue
            ax = axs[dim][dim2] if ndims > 1 else axs[0]
            if dim in lims.keys():
                ax.set_ylim(lims[dim])
            if dim2 in lims.keys():
                ax.set_xlim(lims[dim2])
    if save_name is not None:
        fig.savefig(save_name)
    plt.show()


def _get_ndims(results, vars):
    ndims = int(sum([tuple_prod(v.shape[1:]) for k, v in results.samples.items() if (k in vars)]))
    return ndims


def _get_vars(results, vars):
    if vars is None:
        vars = [k for k, v in results.samples.items()]
    vars = [v for v in vars if v in results.samples.keys()]
    vars = sorted(vars)
    return vars


def plot_samples_development(results, vars=None, save_name=None):
    if save_name is None:
        raise ValueError("In order to plot the animation we must save it.")
    vars = _get_vars(results, vars)
    ndims = _get_ndims(results, vars)
    figsize = min(20, max(4, int(2 * ndims)))
    fig, axs = plt.subplots(ndims, ndims, figsize=(figsize, figsize))
    if ndims == 1:
        axs = [[axs]]
    weights = jnp.exp(results.log_p)
    max_samples = weights.size
    norm = plt.Normalize(weights.min(), weights.max())
    to_colour = lambda w: plt.cm.jet(norm(w))

    def _get_artists(artists, start, stop):
        lims = {}
        dim = 0
        for key in vars:  # sorted(results.samples.keys()):
            n1 = tuple_prod(results.samples[key].shape[1:])
            for i in range(n1):
                samples1 = results.samples[key].reshape((max_samples, -1))[:, i]
                samples1 = samples1[start:stop]
                dim2 = 0
                for key2 in vars:  # sorted(results.samples.keys()):
                    n2 = tuple_prod(results.samples[key2].shape[1:])
                    for i2 in range(n2):
                        ax = axs[dim][dim2]
                        if dim2 > dim:
                            dim2 += 1
                            ax.set_xticks([])
                            ax.set_xticklabels([])
                            ax.set_yticks([])
                            ax.set_yticklabels([])
                            continue
                        if n2 > 1:
                            title2 = "{}[{}]".format(key2, i2)
                        else:
                            title2 = "{}".format(key2)
                        if n1 > 1:
                            title1 = "{}[{}]".format(key, i)
                        else:
                            title1 = "{}".format(key)
                        # ax.set_title('{} {}'.format(title1, title2))
                        if dim == dim2:
                            _, _, new_patches = ax.hist(samples1)
                            artists = artists + list(new_patches)
                            lims[dim] = ax.get_xlim()
                        else:
                            samples2 = results.samples[key2].reshape((max_samples, -1))[:, i2]
                            samples2 = samples2[start:stop]

                            sc = ax.scatter(samples2, samples1, marker='+', c=to_colour(weights[start:stop]), alpha=0.3)
                            artists.append(sc)
                        if dim == ndims - 1:
                            ax.set_xlabel("{}".format(title2))
                        if dim2 == 0:
                            ax.set_ylabel("{}".format(title1))

                        dim2 += 1
                dim += 1
        for dim in range(ndims):
            for dim2 in range(ndims):
                if dim == dim2:
                    continue
                ax = axs[dim][dim2] if ndims > 1 else axs[0]
                if dim in lims.keys():
                    ax.set_ylim(lims[dim])
                if dim2 in lims.keys():
                    ax.set_xlim(lims[dim2])
        return artists

    def init():
        start = 0
        stop = start + results.n_per_sample[start].astype(jnp.int_)
        for i in range(ndims):
            for j in range(ndims):
                axs[i][j].clear()

        artists = []

        artists = _get_artists(artists, start, stop)
        return artists

    def update(start):
        stop = start + results.n_per_sample[start].astype(jnp.int_)
        for i in range(ndims):
            for j in range(ndims):
                axs[i][j].clear()

        artists = []

        artists = _get_artists(artists, start, stop)
        return artists

    ani = FuncAnimation(fig, update, frames=jnp.arange(1,results.num_samples),
                        init_func=init, blit=True)

    ani.save(save_name, fps=results.n_per_sample[0]/2.)
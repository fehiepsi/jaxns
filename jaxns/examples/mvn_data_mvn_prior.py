from jaxns.nested_sampling import NestedSampler
from jaxns.prior_transforms import PriorChain, MVNDiagPrior, MVNPrior
from jaxns.plotting import plot_cornerplot, plot_diagnostics, plot_samples_development
from jax.scipy.linalg import solve_triangular
from jax import random, jit, disable_jit, make_jaxpr
from jax import numpy as jnp
import pylab as plt
from timeit import default_timer


def main():
    def log_normal(x, mean, cov):
        L = jnp.linalg.cholesky(cov)
        dx = x - mean
        dx = solve_triangular(L, dx, lower=True)
        return -0.5 * x.size * jnp.log(2. * jnp.pi) - jnp.sum(jnp.log(jnp.diag(L))) \
               - 0.5 * dx @ dx

    ndims = 15
    prior_mu = 2 * jnp.ones(ndims)
    prior_cov = jnp.diag(jnp.ones(ndims)) ** 2

    data_mu = jnp.ones(ndims)
    data_cov = jnp.diag(jnp.ones(ndims)) ** 2
    data_cov = jnp.where(data_cov == 0., 0.95, data_cov)

    true_logZ = log_normal(data_mu, prior_mu, prior_cov + data_cov)

    post_mu = prior_cov @ jnp.linalg.inv(prior_cov + data_cov) @ data_mu + data_cov @ jnp.linalg.inv(
        prior_cov + data_cov) @ prior_mu
    post_cov = prior_cov @ jnp.linalg.inv(prior_cov + data_cov) @ data_cov

    log_likelihood = lambda x, **kwargs: log_normal(x, data_mu, data_cov)



    def run_with_n(n):
        @jit
        def run(key):
            prior_transform = PriorChain().push(MVNDiagPrior('x', prior_mu, jnp.sqrt(jnp.diag(prior_cov))))
            # prior_transform = LaplacePrior(prior_mu, jnp.sqrt(jnp.diag(prior_cov)))
            # prior_transform = UniformPrior(-20.*jnp.ones(ndims), 20.*jnp.ones(ndims))
            def param_mean(x, **args):
                return x
            def param_covariance(x, **args):
                return jnp.outer(x,x)

            ns = NestedSampler(log_likelihood, prior_transform, sampler_name='slice',
                               x_mean=param_mean,
                               x_cov=param_covariance
                               )
            return ns(key=key,
                      num_live_points=n,
                      max_samples=1e5,
                      collect_samples=True,
                      termination_frac=0.01,
                      stochastic_uncertainty=False,
                      sampler_kwargs=dict(depth=3, num_slices=2))
        # print(len(str(make_jaxpr(run)(random.PRNGKey(0)))))
        #old 720781
        #new 760803
        #new new 648404
        t0 = default_timer()
        results = run(random.PRNGKey(0))
        print('efficiency',results.efficiency)
        print("time to run including compile", default_timer() - t0)
        t0 = default_timer()
        results = run(random.PRNGKey(1))
        print('efficiency', results.efficiency)
        print("time to run not including compile", default_timer() - t0)
        return results

    for n in [1000]:
        # with disable_jit():
        results = run_with_n(n)
        # print(results.marginalised_uncert['x_mean'], results.marginalised_uncert['x_cov'] + jnp.outer(results.marginalised_uncert['x_mean'], results.marginalised_uncert['x_mean']))
        print(results.marginalised['x_mean'], results.marginalised['x_cov'] - jnp.outer(results.marginalised['x_mean'], results.marginalised['x_mean']))
        plt.scatter(n, results.logZ)
        plt.errorbar(n, results.logZ, yerr=results.logZerr)

    plt.hlines(true_logZ, 0, n)
    plt.show()

    # plot_samples_development(results, save_name='./mvn_data_mvn_prior_trajectory.mp4')
    plot_diagnostics(results)
    # plot_cornerplot(results)


    print("True logZ={}".format(true_logZ))
    print("True posterior m={}\nCov={}".format(post_mu, post_cov))


if __name__ == '__main__':

    # import jax.profiler
    # server = jax.profiler.start_server(9999)
    # input("Ready? ")
    main()

# Copyright (c) 2012-2015 The GPy authors (see AUTHORS.txt)
# Licensed under the BSD 3-clause license (see LICENSE.txt)

import numpy as np
import scipy
from ..util.univariate_Gaussian import std_norm_cdf, std_norm_pdf
import scipy as sp
from ..util.misc import safe_exp, safe_square, safe_cube, safe_quad, safe_three_times
from ..core.parameterization import Parameterized
from ..core.parameterization import Param
from ..core.parameterization.transformations import Logexp, Transformation, Logistic

class SigmoidalInverse(Transformation):
    def f(self, x):
        return 2./(1.+np.exp(-1./x))-1.
    
    def finv(self, x):
        return -1./np.log(2./(x+1.)-1)
    
    def gradfactor(self, f, df):
        finv = self.finv(f);
        return -2.*df/((1+np.exp(-1./finv))**2)*np.exp(-1./finv)/(finv**2)
    
    def initialize(self,f):
        if any(f == 0):
            print("Warning: changing parameters to satisfy constraints")
        f[f==0] = np.finfo(float).eps
        return f
        
    def __str__(self):
        return 'sinv'

class GPTransformation(Parameterized):
    """
    Link function class for doing non-Gaussian likelihoods approximation

    :param Y: observed output (Nx1 numpy.darray)

    .. note:: Y values allowed depend on the likelihood_function used

    """
    def __init__(self, name="Transformation"):
        super(GPTransformation, self).__init__(name)
        
    def transf(self,f):
        """
        Gaussian process tranformation function, latent space -> output space
        """
        raise NotImplementedError

    def dtransf_df(self,f):
        """
        derivative of transf(f) w.r.t. f
        """
        raise NotImplementedError

    def d2transf_df2(self,f):
        """
        second derivative of transf(f) w.r.t. f
        """
        raise NotImplementedError

    def d3transf_df3(self,f):
        """
        third derivative of transf(f) w.r.t. f
        """
        raise NotImplementedError

class Identity(GPTransformation):
    """
    .. math::

        g(f) = f

    """
    def transf(self,f):
        return f

    def dtransf_df(self,f):
        return np.ones_like(f)

    def d2transf_df2(self,f):
        return np.zeros_like(f)

    def d3transf_df3(self,f):
        return np.zeros_like(f)

class Probit(GPTransformation):
    """
    .. math::

        g(f) = \\Phi^{-1} (mu)

    """
    def __init__(self, nu=1., fixed = True, name="Probit"):
        super(Probit, self).__init__(name)
        self.nu = Param('nu', float(nu), Logistic(-1e5,1e5))
        if fixed:
            self.nu.constrain_fixed(nu)
        self.link_parameter(self.nu)
        
    def transf(self,f):
        return std_norm_cdf(f*self.nu)

    def dtransf_df(self,f):
        return std_norm_pdf(f*self.nu)*self.nu

    def d2transf_df2(self,f):
        return -(f*self.nu) * std_norm_pdf(f*self.nu)*(self.nu**2)

    def d3transf_df3(self,f):
        return (safe_square(f*self.nu)-1.)*std_norm_pdf(f*self.nu)*(self.nu**3)
    
    def dtransf_dtheta(self, f):
        return std_norm_pdf(f*self.nu)*f
    
    def update_gradients(self, gradient, reset = True):
        if reset:
            self.nu.gradient = gradient
        else:
            self.nu.gradient += gradient
    
    def reset_gradients(self):
        self.nu.gradient = [0]

class Probit2(GPTransformation):
    """
    .. math::

        g(f) = \\Phi^{-1} (mu)

    """
    def __init__(self, nu=1., fixed = True, name="Probit"):
        super(Probit, self).__init__(name)
        self.nu = Param('nu', float(nu), Logexp())
        if fixed:
            self.nu.constrain_fixed(nu)
        self.link_parameter(self.nu)
        
    def transf(self,f):
        return std_norm_cdf(f/self.nu)

    def dtransf_df(self,f):
        return std_norm_pdf(f/self.nu)/self.nu

    def d2transf_df2(self,f):
        return -(f/self.nu) * std_norm_pdf(f/self.nu)/(self.nu**2)

    def d3transf_df3(self,f):
        return (safe_square(f/self.nu)-1.)*std_norm_pdf(f/self.nu)/(self.nu**3)
    
    def dtransf_dtheta(self, f):
        return -std_norm_pdf(f/self.nu)*f/(self.nu**2)
    
    def update_gradients(self, gradient, reset = True):
        if reset:
            self.nu.gradient = gradient
        else:
            self.nu.gradient += gradient
    
    def reset_gradients(self):
        self.nu.gradient = [0]

class Cloglog(GPTransformation):
    """
    Complementary log-log link
    .. math::

        p(f) = 1 - e^{-e^f}

        or

        f = \log (-\log(1-p))

    """
    def transf(self,f):
        ef = safe_exp(f)
        return 1-np.exp(-ef)

    def dtransf_df(self,f):
        ef = safe_exp(f)
        return np.exp(f-ef)

    def d2transf_df2(self,f):
        ef = safe_exp(f)
        return -np.exp(f-ef)*(ef-1.)

    def d3transf_df3(self,f):
        ef = safe_exp(f)
        ef2 = safe_square(ef)
        three_times_ef = safe_three_times(ef)
        r_val = np.exp(f-ef)*(1.-three_times_ef + ef2)
        return r_val

class Log(GPTransformation):
    """
    .. math::

        g(f) = \\log(\\mu)

    """
    def transf(self,f):
        return safe_exp(f)

    def dtransf_df(self,f):
        return safe_exp(f)

    def d2transf_df2(self,f):
        return safe_exp(f)

    def d3transf_df3(self,f):
        return safe_exp(f)

class Log_ex_1(GPTransformation):
    """
    .. math::

        g(f) = \\log(\\exp(\\mu) - 1)

    """
    def transf(self,f):
        return scipy.special.log1p(safe_exp(f))

    def dtransf_df(self,f):
        ef = safe_exp(f)
        return ef/(1.+ef)

    def d2transf_df2(self,f):
        ef = safe_exp(f)
        aux = ef/(1.+ef)
        return aux*(1.-aux)

    def d3transf_df3(self,f):
        ef = safe_exp(f)
        aux = ef/(1.+ef)
        daux_df = aux*(1.-aux)
        return daux_df - (2.*aux*daux_df)

class Reciprocal(GPTransformation):
    def transf(self,f):
        return 1./f

    def dtransf_df(self, f):
        f2 = safe_square(f)
        return -1./f2

    def d2transf_df2(self, f):
        f3 = safe_cube(f)
        return 2./f3

    def d3transf_df3(self,f):
        f4 = safe_quad(f)
        return -6./f4

class Heaviside(GPTransformation):
    """

    .. math::

        g(f) = I_{x \\geq 0}

    """
    def transf(self,f):
        #transformation goes here
        return np.where(f>0, 1, 0)

    def dtransf_df(self,f):
        raise NotImplementedError("This function is not differentiable!")

    def d2transf_df2(self,f):
        raise NotImplementedError("This function is not differentiable!")

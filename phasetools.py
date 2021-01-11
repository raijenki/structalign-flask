# This code is part of phasepack.
# Credits to https://github.com/alimuldal/

import numpy as np
from scipy.fftpack import fftshift, ifftshift, fft2, ifft2


def phasesym(img, nscale=5, norient=6, minWaveLength=3, mult=2.1,
             sigmaOnf=0.55, k=2., polarity=0, noiseMethod=-1):
    """
    This function calculates the phase symmetry of points in an image. This is
    a contrast invariant measure of symmetry. This function can be used as a
    line and blob detector. The greyscale 'polarity' of the lines that you
    want to find can be specified.

    Arguments:
    -----------
    <Name>      <Default>   <Description>
    img             N/A     The input image
    nscale          5       Number of wavelet scales, try values 3-6
    norient         6       Number of filter orientations.
    minWaveLength   3       Wavelength of smallest scale filter.
    mult            2.1     Scaling factor between successive filters.
    sigmaOnf        0.55    Ratio of the standard deviation of the Gaussian
                            describing the log Gabor filter's transfer function
                            in the frequency domain to the filter center
                            frequency.
    k               2.0     No. of standard deviations of the noise energy
                            beyond the mean at which we set the noise threshold
                            point. You may want to vary this up to a value of
                            10 or 20 for noisy images
    polarity        0       Controls 'polarity' of symmetry features to find.
                            1 only return 'bright' features
                            -1 only return 'dark' features
                            0 return both 'bright' and 'dark' features
    noiseMethod     -1      Parameter specifies method used to determine
                            noise statistics.
                            -1 use median of smallest scale filter responses
                            -2 use mode of smallest scale filter responses
                            >=0 use this value as the fixed noise threshold

    Returns:
    ---------
    phaseSym        Phase symmetry image (values between 0 and 1).
    orientation     Orientation image. Orientation in which local symmetry
                    energy is a maximum, in degrees (0-180), angles positive
                    anti-clockwise. Note that the orientation info is quantized
                    by the number of orientations
    totalEnergy     Un-normalised raw symmetry energy which may be more to your
                    liking.
    T               Calculated noise threshold (can be useful for diagnosing
                    noise characteristics of images). Once you know this you
                    can then specify fixed thresholds and save some computation
                    time.

    The convolutions are done via the FFT. Many of the parameters relate to the
    specification of the filters in the frequency plane. The values do not seem
    to be very critical and the defaults are usually fine. You may want to
    experiment with the values of 'nscales' and 'k', the noise compensation
    factor.

    Notes on filter settings to obtain even coverage of the spectrum:
    sigmaOnf    .85   mult 1.3
    sigmaOnf    .75   mult 1.6  (filter bandwidth ~1 octave)
    sigmaOnf    .65   mult 2.1
    sigmaOnf    .55   mult 3    (filter bandwidth ~2 octaves)

    For maximum speed the input image should have dimensions that correspond to
    powers of 2, but the code will operate on images of arbitrary size.

    See also:   phasesymmono, which uses monogenic filters for improved
                speed, but does not return an orientation image.

    References:
    ------------
    Peter Kovesi, "Symmetry and Asymmetry From Local Phase" AI'97, Tenth
    Australian Joint Conference on Artificial Intelligence. 2 - 4 December
    1997. <http://www.cs.uwa.edu.au/pub/robvis/papers/pk/ai97.ps.gz.>

    Peter Kovesi, "Image Features From Phase Congruency". Videre: A Journal of
    Computer Vision Research. MIT Press. Volume 1, Number 3, Summer 1999
    <http://mitpress.mit.edu/e-journals/Videre/001/v13.html>

    """

    if img.dtype not in ['float32', 'float64']:
        img = np.float64(img)
        imgdtype = 'float64'
    else:
        imgdtype = img.dtype

    if img.ndim == 3:
        img = img.mean(2)
    rows, cols = img.shape

    epsilon = 1E-4  # used to prevent /0.
    IM = fft2(img)  # Fourier transformed image

    zeromat = np.zeros((rows, cols), dtype=imgdtype)

    # Matrix for accumulating weighted phase congruency values (energy).
    totalEnergy = zeromat.copy()

    # Matrix for accumulating filter response amplitude values.
    totalSumAn = zeromat.copy()

    # Matrix storing orientation with greatest energy for each pixel.
    orientation = zeromat.copy()

    # Pre-compute some stuff to speed up filter construction

    # Set up X and Y matrices with ranges normalised to +/- 0.5
    if (cols % 2):
        xvals = np.arange(-(cols - 1) / 2.,
                          ((cols - 1) / 2.) + 1) / float(cols - 1)
    else:
        xvals = np.arange(-cols / 2., cols / 2.) / float(cols)

    if (rows % 2):
        yvals = np.arange(-(rows - 1) / 2.,
                          ((rows - 1) / 2.) + 1) / float(rows - 1)
    else:
        yvals = np.arange(-rows / 2., rows / 2.) / float(rows)

    x, y = np.meshgrid(xvals, yvals, sparse=True)

    # normalised distance from centre
    radius = np.sqrt(x * x + y * y)

    # polar angle (-ve y gives +ve anti-clockwise angles)
    theta = np.arctan2(-y, x)

    # Quadrant shift radius and theta so that filters are constructed with 0
    # frequency at the corners
    radius = ifftshift(radius)
    theta = ifftshift(theta)

    # Get rid of the 0 radius value at the 0 frequency point (now at top-left
    # corner) so that taking the log of the radius will not cause trouble.
    radius[0, 0] = 1.

    sintheta = np.sin(theta)
    costheta = np.cos(theta)

    del x, y, theta

    # Construct a bank of log-Gabor filters at different spatial scales

    # Filters are constructed in terms of two components:
    # 1) The radial component, which controls the frequency band that the
    #    filter responds to
    # 2) The angular component, which controls the orientation that the filter
    #    responds to.
    # The two components are multiplied together to construct the overall
    # filter.

    # Construct the radial filter components... First construct a low-pass
    # filter that is as large as possible, yet falls away to zero at the
    # boundaries. All log Gabor filters are multiplied by this to ensure no
    # extra frequencies at the 'corners' of the FFT are incorporated as this
    # seems to upset the normalisation process when calculating phase
    # congrunecy.
    lp = _lowpassfilter([rows, cols], .4, 10)
    # Radius .4, 'sharpness' 10

    logGaborDenom = 2. * np.log(sigmaOnf) ** 2.
    logGabor = []

    for ss in range(nscale):
        wavelength = minWaveLength * mult ** (ss)

        # centre of frequency filter
        fo = 1. / wavelength

        # log Gabor
        logRadOverFo = np.log(radius / fo)
        tmp = np.exp(-(logRadOverFo * logRadOverFo) / logGaborDenom)

        # apply low-pass filter
        tmp = tmp * lp

        # set the value at the 0 frequency point of the filter back to
        # zero (undo the radius fudge).
        tmp[0, 0] = 0.

        logGabor.append(tmp)

    # MAIN LOOP
    # for each orientation...
    for oo in range(norient):

        # Construct the angular filter spread function
        angl = oo * (np.pi / norient)

        # For each point in the filter matrix calculate the angular distance
        # from the specified filter orientation. To overcome the angular wrap-
        # around problem sine difference and cosine difference values are first
        # computed and then the arctan2 function is used to determine angular
        # distance.

        # difference in sine and cosine
        ds = sintheta * np.cos(angl) - costheta * np.sin(angl)
        dc = costheta * np.cos(angl) + sintheta * np.sin(angl)

        # absolute angular difference
        dtheta = np.abs(np.arctan2(ds, dc))

        # Scale theta so that cosine spread function has the right wavelength
        # and clamp to pi.
        np.clip(dtheta * norient / 2., a_min=0, a_max=np.pi, out=dtheta)

        # The spread function is cos(dtheta) between -pi and pi. We add 1, and
        # then divide by 2 so that the value ranges 0-1
        spread = (np.cos(dtheta) + 1.) / 2.

        # Initialize accumulators
        sumAn_ThisOrient = zeromat.copy()
        Energy_ThisOrient = zeromat.copy()

        # for each scale...
        for ss in range(nscale):

            # Multiply radial and angular components to get filter
            filt = logGabor[ss] * spread

            # Convolve image with even and odd filters
            EO = ifft2(IM * filt)

            # Sum of amplitudes ofeven & odd filter responses
            sumAn_ThisOrient += np.abs(EO)

            # At the smallest scale estimate noise characteristics from the
            # distribution of the filter amplitude responses stored in sumAn.
            # tau is the Rayleigh parameter that is used to describe the
            # distribution.
            if ss == 0:
                # Use median to estimate noise statistics
                if noiseMethod == -1:
                    tau = np.median(
                        sumAn_ThisOrient.flatten()) / np.sqrt(np.log(4))

                # Use the mode to estimate noise statistics
                elif noiseMethod == -2:
                    tau = _rayleighmode(sumAn_ThisOrient.flatten())

            # Now calculate the phase symmetry measure

            # look for 'white' and 'black' spots
            if polarity == 0:
                Energy_ThisOrient += np.abs(np.real(EO)) - np.abs(np.imag(EO))

            # just look for 'white' spots
            elif polarity == 1:
                Energy_ThisOrient += np.real(EO) - np.abs(np.imag(EO))

            # just look for 'black' spots
            elif polarity == -1:
                Energy_ThisOrient += -np.real(EO) - np.abs(np.imag(EO))

        # Automatically determine noise threshold

        # Assuming the noise is Gaussian the response of the filters to noise
        # will form Rayleigh distribution. We use the filter responses at the
        # smallest scale as a guide to the underlying noise level because the
        # smallest scale filters spend most of their time responding to noise,
        # and only occasionally responding to features. Either the median, or
        # the mode, of the distribution of filter responses can be used as a
        # robust statistic to estimate the distribution mean and standard
        # deviation as these are related to the median or mode by fixed
        # constants. The response of the larger scale filters to noise can then
        # be estimated from the smallest scale filter response according to
        # their relative bandwidths.

        # This code assumes that the expected reponse to noise on the phase
        # congruency calculation is simply the sum of the expected noise
        # responses of each of the filters. This is a simplistic overestimate,
        # however these two quantities should be related by some constant that
        # will depend on the filter bank being used. Appropriate tuning of the
        # parameter 'k' will allow you to produce the desired output.

        # fixed noise threshold
        if noiseMethod >= 0:
            T = noiseMethod

        # Estimate the effect of noise on the sum of the filter responses as
        # the sum of estimated individual responses (this is a simplistic
        # overestimate). As the estimated noise response at succesive scales is
        # scaled inversely proportional to bandwidth we have a simple geometric
        # sum.
        else:
            totalTau = tau * (1. - (1. / mult) ** nscale) / (1. - (1. / mult))

            # Calculate mean and std dev from tau using fixed relationship
            # between these parameters and tau. See
            # <http://mathworld.wolfram.com/RayleighDistribution.html>
            EstNoiseEnergyMean = totalTau * np.sqrt(np.pi / 2.)
            EstNoiseEnergySigma = totalTau * np.sqrt((4 - np.pi) / 2.)

            # Noise threshold, must be >= epsilon
            T = np.maximum(
                EstNoiseEnergyMean + k * EstNoiseEnergySigma,
                epsilon)

        # Apply noise threshold,  this is effectively wavelet denoising via
        # soft thresholding. Note 'Energy_ThisOrient' will have -ve values.
        # These will be floored out at the final normalization stage.
        Energy_ThisOrient -= T

        # Update accumulator matrix for sumAn and totalEnergy
        totalSumAn += sumAn_ThisOrient
        totalEnergy += Energy_ThisOrient

        # Update orientation matrix by finding image points where the energy in
        # this orientation is greater than in any previous orientation (the
        # change matrix) and then replacing these elements in the orientation
        # matrix with the current orientation number.
        if oo == 0:
            maxEnergy = Energy_ThisOrient
        else:
            change = Energy_ThisOrient > maxEnergy
            orientation = oo * change + orientation * (~change)
            maxEnergy = np.maximum(Energy_ThisOrient, maxEnergy)

    # Normalize totalEnergy by the totalSumAn to obtain phase symmetry
    # totalEnergy is floored at 0 to eliminate -ve values
    totalEnergy = np.maximum(totalEnergy, 0)
    phaseSym = totalEnergy / (totalSumAn + epsilon)

    # Convert orientation matrix values to degrees
    orientation = np.fix(orientation * (180. / norient))

    return phaseSym

def _lowpassfilter(size, cutoff, n):
    """
    Constructs a low-pass Butterworth filter:

        f = 1 / (1 + (w/cutoff)^2n)

    usage:  f = lowpassfilter(sze, cutoff, n)

    where:  size    is a tuple specifying the size of filter to construct
            [rows cols].
        cutoff  is the cutoff frequency of the filter 0 - 0.5
        n   is the order of the filter, the higher n is the sharper
            the transition is. (n must be an integer >= 1). Note
            that n is doubled so that it is always an even integer.

    The frequency origin of the returned filter is at the corners.
    """

    if cutoff < 0. or cutoff > 0.5:
        raise Exception('cutoff must be between 0 and 0.5')
    elif n % 1:
        raise Exception('n must be an integer >= 1')
    if len(size) == 1:
        rows = cols = size
    else:
        rows, cols = size

    if (cols % 2):
        xvals = np.arange(-(cols - 1) / 2.,
                          ((cols - 1) / 2.) + 1) / float(cols - 1)
    else:
        xvals = np.arange(-cols / 2., cols / 2.) / float(cols)

    if (rows % 2):
        yvals = np.arange(-(rows - 1) / 2.,
                          ((rows - 1) / 2.) + 1) / float(rows - 1)
    else:
        yvals = np.arange(-rows / 2., rows / 2.) / float(rows)

    x, y = np.meshgrid(xvals, yvals, sparse=True)
    radius = np.sqrt(x * x + y * y)

    return ifftshift(1. / (1. + (radius / cutoff) ** (2. * n)))
	
def rayleighmode(data, nbins=50):
    """
    Computes mode of a vector/matrix of data that is assumed to come from a
    Rayleigh distribution.
    usage:  rmode = rayleighmode(data, nbins)
    where:  data    data assumed to come from a Rayleigh distribution
            nbins   optional number of bins to use when forming histogram
                    of the data to determine the mode.
    Mode is computed by forming a histogram of the data over 50 bins and then
    finding the maximum value in the histogram. Mean and standard deviation
    can then be calculated from the mode as they are related by fixed
    constants.
        mean = mode * sqrt(pi/2)
        std dev = mode * sqrt((4-pi)/2)
    See:
        <http://mathworld.wolfram.com/RayleighDistribution.html>
        <http://en.wikipedia.org/wiki/Rayleigh_distribution>
    """
    n, edges = np.histogram(data, nbins)
    ind = np.argmax(n)
    return (edges[ind] + edges[ind + 1]) / 2.


def perfft2(im, compute_P=True, compute_spatial=False):
    """
    Moisan's Periodic plus Smooth Image Decomposition. The image is
    decomposed into two parts:
        im = s + p
    where 's' is the 'smooth' component with mean 0, and 'p' is the 'periodic'
    component which has no sharp discontinuities when one moves cyclically
    across the image boundaries.
    useage: S, [P, s, p] = perfft2(im)
    where:  im      is the image
            S       is the FFT of the smooth component
            P       is the FFT of the periodic component, returned if
                    compute_P (default)
            s & p   are the smooth and periodic components in the spatial
                    domain, returned if compute_spatial
    By default this function returns `P` and `S`, the FFTs of the periodic and
    smooth components respectively. If `compute_spatial=True`, the spatial
    domain components 'p' and 's' are also computed.
    This code is adapted from Lionel Moisan's Scilab function 'perdecomp.sci'
    "Periodic plus Smooth Image Decomposition" 07/2012 available at:
        <http://www.mi.parisdescartes.fr/~moisan/p+s>
    """

    if im.dtype not in ['float32', 'float64']:
        im = np.float64(im)

    rows, cols = im.shape

    # Compute the boundary image which is equal to the image discontinuity
    # values across the boundaries at the edges and is 0 elsewhere
    s = np.zeros_like(im)
    s[0, :] = im[0, :] - im[-1, :]
    s[-1, :] = -s[0, :]
    s[:, 0] = s[:, 0] + im[:, 0] - im[:, -1]
    s[:, -1] = s[:, -1] - im[:, 0] + im[:, -1]

    # Generate grid upon which to compute the filter for the boundary image
    # in the frequency domain.  Note that cos is cyclic hence the grid
    # values can range from 0 .. 2*pi rather than 0 .. pi and then pi .. 0
    x, y = (2 * np.pi * np.arange(0, v) / float(v) for v in (cols, rows))
    cx, cy = np.meshgrid(x, y)

    denom = (2. * (2. - np.cos(cx) - np.cos(cy)))
    denom[0, 0] = 1.     # avoid / 0

    S = fft2(s) / denom
    S[0, 0] = 0      # enforce zero mean

    if compute_P or compute_spatial:

        P = fft2(im) - S

        if compute_spatial:
            s = ifft2(S).real
            p = im - s

            return S, P, s, p
        else:
            return S, P
    else:
        return S
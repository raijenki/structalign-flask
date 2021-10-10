import numpy as np
import tifffile
import cv2
import os
from zipfile import ZipFile 
from app import app
from osgeo import gdal, gdalnumeric, ogr, osr
from phasetools import phasesym
from matplotlib import pyplot as plt
from matplotlib.pyplot import savefig
from skimage.color import rgb2gray
from skimage.filters import gaussian, threshold_otsu, rank
from skimage.filters.rank import entropy
from skimage.io import imsave, imread
from skimage.morphology import square
from skimage.util import img_as_ubyte
from skimage.morphology import skeletonize

def transform():
    files = []
    with open('list.txt', r) as f:
        files = f.readlines()
    f.close()

    for file in files:
        print("Processing " + file + "...")
        # Import file
        data = tifffile.imread(file)
        # Convert 3-band RGB to 1-band grayscale
        grayscale = rgb2gray(data)

        # Calculate standard deviation
        mult_1 = np.multiply(grayscale, grayscale)
        blur_1 = gaussian(mult_1, sigma=(9, 9), truncate=3.5, multichannel=False)
        blur_2 = gaussian(grayscale, sigma=(9, 9), truncate=3.5, multichannel=False)
        mult_2 = np.multiply(blur_2, blur_2)
        std_hat = np.sqrt(blur_1 - mult_2)

        # Calculate entropy
        sigma_hat = entropy(std_hat, square(9))

        # Phase symmetry
        psym = phasesym(sigma_hat)

        # Threshold
        selem = square(9)
        local_otsu = rank.otsu(psym, selem)
        threshold_global_otsu = threshold_otsu(psym)
        global_otsu = (psym >= threshold_global_otsu)

        # Skeletonize and invert colors
        skeleton = skeletonize(global_otsu, method='lee')

        skeleton[skeleton == 255] = 1
        skeleton[skeleton == 0] = 255
        skeleton[skeleton == 1] = 0

        # Save intermediate files as png
        plt.imsave(alignedname, skeleton, cmap=plt.cm.gray, dpi=300)
        print("File " + file + " done!")

if __name__ == '__main__':
    transform()
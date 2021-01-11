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

def calculate(imgfile, uuid_fname, usr_nscale, usr_norient, usr_minWaveLength, usr_mult, usr_sigmaOnf, usr_k, usr_polarity, usr_noiseMethod):
    
    usr_nscale = int(usr_nscale)
    usr_norient = int(usr_norient)
    usr_minWaveLength = int(usr_minWaveLength)
    usr_mult = float(usr_mult) 
    usr_sigmaOnf = float(usr_sigmaOnf) 
    usr_k = float(usr_k) 
    usr_polarity = int(usr_polarity) 
    usr_noiseMethod = int(usr_noiseMethod)
    
    # Names var for later use
    TMP_FOLDER = '/app/app/static/'
    pngfile = os.path.join(TMP_FOLDER, uuid_fname + '_file.png') 
    alignedname = os.path.join(TMP_FOLDER, uuid_fname + '_align.png')
    alignedblackname = os.path.join(TMP_FOLDER, uuid_fname + '_blackalign.png')  
    fusedname = os.path.join(TMP_FOLDER, uuid_fname + '_fused.png') 

    # Import file
    data = tifffile.imread(imgfile)
    
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
    psym = phasesym(sigma_hat, nscale=usr_nscale, norient=usr_norient, minWaveLength=usr_minWaveLength, mult=usr_mult, sigmaOnf=usr_sigmaOnf, k=usr_k, polarity=usr_polarity, noiseMethod=usr_noiseMethod)

    # Threshold
    selem = square(9)
    local_otsu = rank.otsu(psym, selem)
    threshold_global_otsu = threshold_otsu(psym)
    global_otsu = (psym >= threshold_global_otsu)

    # Skeletonize and invert colors
    skeleton = skeletonize(global_otsu, method='lee')
    plt.imsave(alignedblackname, skeleton, cmap=plt.cm.gray, dpi=300)

    skeleton[skeleton == 255] = 1
    skeleton[skeleton == 0] = 255
    skeleton[skeleton == 1] = 0

    # Save intermediate files as png
    plt.imsave(pngfile, data)
    plt.imsave(alignedname, skeleton, cmap=plt.cm.gray, dpi=300)

    # Join both images  for display
    img1 = cv2.imread(pngfile)
    img2 = cv2.imread(alignedname)

    rows,cols,channels = img2.shape
    roi = img1[0:rows, 0:cols ]

    # Now create a mask of logo and create its inverse mask also
    img2gray = cv2.cvtColor(img2,cv2.COLOR_BGR2GRAY)
    ret, mask = cv2.threshold(img2gray, 10, 255, cv2.THRESH_BINARY_INV)
    mask_inv = cv2.bitwise_not(mask)

    # Now black-out the area of logo in ROI
    img1_bg = cv2.bitwise_and(roi,roi,mask = mask_inv)

    # Take only region of logo from logo image.
    img2_fg = cv2.bitwise_and(img2,img2,mask = mask)

    # Put logo in ROI and modify the main image
    dst = cv2.add(img1_bg,img2_fg)
    img1[0:rows, 0:cols ] = dst
    cv2.imwrite(fusedname, img1)

def make_shp(imgname):
    STATIC_FOLDER = '/app/app/static/'
    app.config['STATIC_FOLDER'] = STATIC_FOLDER
    origname = STATIC_FOLDER + imgname + '.tif'
    alignedname = STATIC_FOLDER + imgname + '_blackalign.png'
    alignedname_tif = STATIC_FOLDER + imgname + '_blackalign.tif'
    zipname =  STATIC_FOLDER + imgname + '.zip'

    ziplist = [ STATIC_FOLDER + imgname + '_shape.dbf',
    STATIC_FOLDER + imgname + '_shape.prj',
    STATIC_FOLDER + imgname + '_shape.shp',
    STATIC_FOLDER + imgname + '_shape.shx'
    ]

    source = gdal.Open(origname)
    srcbnd = np.array(source.GetRasterBand(1).ReadAsArray())
    alignments = gdal.Open(alignedname)
    alignband = np.array(alignments.GetRasterBand(1).ReadAsArray())

    dst_ds = gdal.GetDriverByName('GTiff').Create(alignedname_tif, srcbnd.shape[1], srcbnd.shape[0], 3, gdal.GDT_Byte, options = ['PHOTOMETRIC=RGB', 'PROFILE=GeoTIFF',])
    gdalnumeric.CopyDatasetInfo(source, dst_ds)
    dst_ds.GetRasterBand(1).WriteArray(alignband)
    dst_ds.FlushCache()

    src_ds = dst_ds
    proj = osr.SpatialReference(wkt=src_ds.GetProjection())
    dst_layername = imgname + "_shape"
    srcband = src_ds.GetRasterBand(1)

    drv = ogr.GetDriverByName("ESRI Shapefile")
    dst_ds = drv.CreateDataSource( STATIC_FOLDER + dst_layername + ".shp" )
    dst_layer = dst_ds.CreateLayer(dst_layername, proj, geom_type=ogr.wkbMultiLineString)
    gdal.Polygonize( srcband, None, dst_layer, -1, [], callback=None )
    
    dst_ds.FlushCache()

    with ZipFile(zipname,'w') as zip: 
        for file in ziplist:
            zip.write(file)

def make_gtif(imgname):
    STATIC_FOLDER = '/app/app/static/'
    app.config['STATIC_FOLDER'] = STATIC_FOLDER
    origname = os.path.join(app.config['STATIC_FOLDER'], imgname + '.tif')
    fusedname = os.path.join(STATIC_FOLDER, imgname + '_fused.png') 
    gtif = os.path.join(STATIC_FOLDER, imgname + '_geotiff.tif') 


    source = gdal.Open(origname)
    pngfusion = gdal.Open(fusedname)
    R = np.array(pngfusion.GetRasterBand(1).ReadAsArray())
    G = np.array(pngfusion.GetRasterBand(2).ReadAsArray())
    B = np.array(pngfusion.GetRasterBand(3).ReadAsArray())

    dst_ds = gdal.GetDriverByName('GTiff').Create(gtif, R.shape[1], R.shape[0], 3, gdal.GDT_Byte, options = ['PHOTOMETRIC=RGB', 'PROFILE=GeoTIFF', 'COMPRESS=LZW'])
    gdalnumeric.CopyDatasetInfo(source, dst_ds)
    dst_ds.GetRasterBand(1).WriteArray(R)
    dst_ds.GetRasterBand(2).WriteArray(G)
    dst_ds.GetRasterBand(3).WriteArray(B)
    dst_ds.FlushCache()
    dst_ds = None

def make_alignedtif(imgname):
    STATIC_FOLDER = '/app/app/static/'
    app.config['STATIC_FOLDER'] = STATIC_FOLDER
    origname = STATIC_FOLDER + imgname + '.tif'
    alignedname = STATIC_FOLDER + imgname + '_align.png'
    alignedname_tif = STATIC_FOLDER + imgname + '_align.tif'


    source = gdal.Open(origname)
    srcbnd = np.array(source.GetRasterBand(1).ReadAsArray())
    alignments = gdal.Open(alignedname)
    alignband = np.array(alignments.GetRasterBand(1).ReadAsArray())

    dst_ds = gdal.GetDriverByName('GTiff').Create(alignedname_tif, srcbnd.shape[1], srcbnd.shape[0], 3, gdal.GDT_Byte, options = ['PHOTOMETRIC=RGB', 'PROFILE=GeoTIFF',])
    gdalnumeric.CopyDatasetInfo(source, dst_ds)
    dst_ds.GetRasterBand(1).WriteArray(alignband)
    dst_ds.GetRasterBand(1).SetNoDataValue(255)
    dst_ds.FlushCache()

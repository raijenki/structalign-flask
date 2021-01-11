# structalign-flask

** Code is not optimized for production yet**

This is a flask application built for structural alignment detections on the premise of Geophysics as a Service. It uses the methodology described by Holden et al. (2012) as basis of its algorithm. The pipeline consists into image grayscaling, calculating standard deviation and entropy, phase symmetry, thresholding and skeletonization.

 The inputs are geotiff files while it outputs shapefiles or fused geotiff files. An example of how it works can be seen here: [input](https://i.imgur.com/ktoOW5fh.jpg) and [output](https://i.imgur.com/yi6wGZnh.jpg) 
 
 A deployed version can be seen [here](https://magstruct.herokuapp.com/).

## Running

Deploying is a matter of installing all requirements listed on `requirements.txt` and changing the absolute paths that are on `structural.py` and `app/views.py`. After this, just set the environment variable `FLASK_APP=run.py` and use the `flask run` command. 

If deploying on Heroku, both buildpacks [raijenki/heroku-geo-buildpack-apt](https://github.com/raijenki/heroku-geo-buildpack-apt) and [heroku/heroku-buildpack-python](https://github.com/heroku/heroku-buildpack-python) must be used in this order.

 ## References
 E. Holden, J. C. Wong, P. Kovesi, D. Wedge, M. Dentith and L. Bagas. Identifying structural complexity in aeromagnetic data: An image analysis approach to greenfields gold exploration. Ore Geology Reviews, v. 46, p. 47-59. Elsevier, 2012.
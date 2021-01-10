from flask import render_template, flash, request, redirect, url_for, safe_join, send_file, send_from_directory, abort
from app import app
import os
import uuid
from werkzeug.utils import secure_filename
from structural import calculate, make_gtif, make_shp

UPLOAD_FOLDER = '/app/tmp/'
STATIC_FOLDER = '/app/static/'
FULL_STATICPATH = '/app/static/'
ALLOWED_EXTENSIONS = {'tif'}
app.config['FULL_STATICPATH'] = FULL_STATICPATH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['STATIC_FOLDER'] = STATIC_FOLDER
URL = r'http://magstruct.herokuapp.com'

@app.route('/')  
def index():  
    return render_template("index.html") 

@app.route('/faq')  
def faq():  
    return render_template("faq.html") 

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        for f in request.files.getlist('file'):
            uuid_fname = str(uuid.uuid1())
            uuid_fname_tif = uuid_fname + '.tif'
            f = request.files['file']  
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], uuid_fname_tif))
    return redirect(url_for('editor', uuid_fname=uuid_fname, usr_nscale=5, usr_norient=6, usr_minWaveLength=3, usr_mult=2.1, usr_sigmaOnf=0.55, usr_k=20.0, usr_polarity=0, usr_noiseMethod=-1))

@app.route('/editor/<uuid_fname>?usr_nscale=<usr_nscale>&usr_norient=<usr_norient>&usr_minWaveLength=<usr_minWaveLength>&usr_mult=<usr_mult>&usr_sigmaOnf=<usr_sigmaOnf>&usr_k=<usr_k>&usr_polarity=<usr_polarity>&usr_noiseMethod=<usr_noiseMethod>', methods=['GET'])  
def editor(uuid_fname, usr_nscale, usr_norient, usr_minWaveLength, usr_mult, usr_sigmaOnf, usr_k, usr_polarity, usr_noiseMethod):  
    #if request.method == 'POST':  
    uuid_fname_tif = uuid_fname + '.tif'
    uuid_fname_png = uuid_fname + '_fused.png'
    fimg = os.path.join(app.config['UPLOAD_FOLDER'], uuid_fname_tif)
    calculate(fimg, uuid_fname, usr_nscale, usr_norient, usr_minWaveLength, usr_mult, usr_sigmaOnf, usr_k, usr_polarity, usr_noiseMethod)
    return render_template("editor.html", imgdir=uuid_fname_png, id=uuid_fname, usr_nscale=usr_nscale, usr_norient=usr_norient, usr_minWaveLength=usr_minWaveLength, usr_mult=usr_mult, usr_sigmaOnf=usr_sigmaOnf, usr_k=usr_k, usr_polarity=usr_polarity, usr_noiseMethod=usr_noiseMethod)  

@app.route('/refresh_editor', methods=['POST'])
def refresh_editor():
    uuid_fname = request.form['uuid_fname']
    usr_nscale = request.form['usrnscale']
    usr_norient = request.form['usrnorient']
    usr_minWaveLength = request.form['usrminWaveLength']
    usr_mult = request.form['usrmult']
    usr_sigmaOnf = request.form['usrsigmaOnf']
    usr_k = request.form['usrk']
    usr_polarity = request.form['usrpolarity']
    usr_noiseMethod = request.form['usrnoiseMethod']
    return redirect(url_for('editor', uuid_fname=uuid_fname, usr_nscale=usr_nscale, usr_norient=usr_norient, usr_minWaveLength=usr_minWaveLength, usr_mult=usr_mult, usr_sigmaOnf=usr_sigmaOnf, usr_k=usr_k, usr_polarity=usr_polarity, usr_noiseMethod=usr_noiseMethod))


@app.route('/makepng/<uuid_fname>')
def return_png(uuid_fname):
    try:
        uuid_fname_png = uuid_fname + '_file.png'
        return render_template("download.html", url=URL, file=uuid_fname_png)
    except FileNotFoundError:
        abort(404)

@app.route('/maketif/<uuid_fname>')
def return_tif(uuid_fname):
    try:
        uuid_fname_gtif = uuid_fname + '_geotiff.tif'
        make_gtif(uuid_fname)
        return render_template("download.html", url=URL, file=uuid_fname_gtif)
    except FileNotFoundError:
        abort(404)

@app.route('/makeshp/<uuid_fname>')
def return_shp(uuid_fname):
    try:
        uuid_fname_zip = uuid_fname + '.zip'
        make_shp(uuid_fname)
        return render_template("download.html", url=URL, file=uuid_fname_zip)
    except FileNotFoundError:
        abort(404)

@app.route('/download/<uuid_fname>', methods=['GET'])
def return_file(uuid_fname):
    safe_path = safe_join(app.config["FULL_STATICPATH"], uuid_fname)
    try:
	    return send_file(safe_path, as_attachment=True)
    except FileNotFoundError:
        abort(404)
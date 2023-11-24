from gevent import monkey
monkey.patch_all()

import subprocess
import os

from flask import Flask
from werkzeug.utils import secure_filename
from flask_restful import Api, Resource, request

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
api = Api(app)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000
app.config['UPLOAD_FOLDER'] = os.path.join('data', 'uploads')

@api.resource('/print')
class Print(Resource):
    def post(self):
        file = request.files['file']
        if file.filename == '':
            return {'error': 'No file selected'}, 400

        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            subprocess.Popen(f'lpr -o media=A4 -o prettyprint -o page-border=single -o fit-to-page {os.path.join(app.config["UPLOAD_FOLDER"], filename)}')
            return {'success': True}, 200
        else:
            return {'error': 'No file selected'}, 400

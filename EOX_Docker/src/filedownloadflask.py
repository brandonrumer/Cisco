#!/usr/local/bin/python3

import zipfile
import os
from flask import send_file, Flask, send_from_directory

app = Flask(__name__)

@app.route('/')


def download_all():

    return send_file('/src/export/outfile.csv',
            mimetype = 'csv',
            attachment_filename= 'outfile.csv',
            as_attachment = True)


if __name__ == '__main__':
    app.run(host = '0.0.0.0')

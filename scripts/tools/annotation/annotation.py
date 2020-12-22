#!/usr/bin/env python
"""
The annotation script allows you to annotate the frames generated by `prepare_annotation.py` for a given class and
split in the data-set folder.

Usage:
  annotation.py --data_path=DATA_PATH --split=SPLIT --label=LABEL
  annotation.py (-h | --help)

Options:
  --data_path=DATA_PATH     Complete or relative path to the data-set folder
  --split=SPLIT             Type of split to collect videos from, either `train` or `valid`
  --label=LABEL             Class-label to get the videos for annotation
"""


import glob
import json
import numpy as np
import os

from docopt import docopt
from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import send_from_directory
from flask import url_for
from joblib import dump
from joblib import load
from os.path import join
from sklearn.linear_model import LogisticRegression


app = Flask(__name__)
app.secret_key = 'd66HR8dç"f_-àgjYYic*dh'


def extension_ok(filename):
    """ Returns `True` if the file has a valid image extension. """
    return '.' in filename and filename.rsplit('.', 1)[1] in ('png', 'jpg', 'jpeg', 'gif', 'bmp')


@app.route('/annotate/')
def prepare_gridview():
    """Gets the data and creates the HTML template with all videos for the given class-label."""
    folder_id = zip(videos, list(range(len(videos))))
    return render_template('up_folder.html', folders=folder_id)


@app.route('/annotate/<idx>')
def annotate(idx):
    """For the given class-label, this shows all the frames for annotating the selected video."""
    idx = int(idx)
    features = np.load(join(features_dir, videos[idx] + ".npy"))
    features = features.mean(axis=(2, 3))

    if logreg is not None:
        classes = list(logreg.predict(features))
    else:
        classes = [0] * len(features)

    # The list of images in the folder
    images = [image for image in glob.glob(join(frames_dir, videos[idx] + '/*'))
              if extension_ok(image)]

    indexes = [int(image.split('.')[0].split('/')[-1]) for image in images]
    n_images = len(indexes)

    images = [[image.replace(frames_dir, ''), ii] for ii, image in sorted(zip(indexes, images))]
    images = [[image[0], image[1], _class] for image, _class in zip(images, classes)]

    chunk_size = 5
    images = np.array_split(images, np.arange(chunk_size, len(images), chunk_size))
    images = [list(image) for image in images]

    return render_template('up_list.html', images=images, idx=idx, fps=16,
                           n_images=n_images, video_name=videos[idx])


@app.route('/response', methods=['POST'])
def response():
    if request.method == 'POST':
        data = request.form  # a multi-dict containing POST data
        print(data)
        idx = int(data['idx'])
        fps = float(data['fps'])
        next_frame_idx = idx + 1

        description = {'file': videos[idx] + ".mp4", 'fps': fps}

        out_annotation = os.path.join(tags_dir, videos[idx] + ".json")
        time_annotation = []

        for i in range(int(data['n_images'])):
            time_annotation.append(int(data[str(i)]))

        description['time_annotation'] = time_annotation
        json.dump(description, open(out_annotation, 'w'))

        if next_frame_idx >= len(videos):
            return redirect(url_for('prepare_gridview'))

    return redirect(url_for('annotate', idx=next_frame_idx))


@app.route('/train_logreg', methods=['POST'])
def train_logreg():
    global logreg

    if request.method == 'POST':
        data = request.form  # a multi-dict containing POST data
        idx = int(data['idx'])
        annotations = os.listdir(tags_dir)
        class_weight = {0: 0.5}

        if annotations:
            features = [join(features_dir, x.replace('.json', '.npy')) for x in annotations]
            annotations = [join(tags_dir, x) for x in annotations]
            X = []
            y = []

            for feature in features:
                feature = np.load(feature)

                for f in feature:
                    X.append(f.mean(axis=(1, 2)))

            for annotation in annotations:
                annotation = json.load(open(annotation, 'r'))['time_annotation']
                pos1 = np.where(np.array(annotation).astype(int) == 1)[0]

                if len(pos1) > 0:
                    class_weight.update({1: 2})

                    for p in pos1:
                        if p + 1 < len(annotation):
                            annotation[p + 1] = 1

                pos1 = np.where(np.array(annotation).astype(int) == 2)[0]

                if len(pos1) > 0:
                    class_weight.update({2: 2})

                    for p in pos1:
                        if p + 1 < len(annotation):
                            annotation[p + 1] = 2

                for a in annotation:
                    y.append(a)

            X = np.array(X)
            y = np.array(y)
            logreg = LogisticRegression(C=0.1, class_weight=class_weight)
            logreg.fit(X, y)
            dump(logreg, logreg_path)

    return redirect(url_for('annotate', idx=idx))


@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r


@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(frames_dir, filename, as_attachment=True)


if __name__ == '__main__':
    # Parse arguments
    args = docopt(__doc__)
    dataset_path = args['--data_path']
    split = args['--split']
    label = args['--label']

    features_dir = dataset_path + f"features_{split}/{label}/"
    frames_dir = dataset_path + f"frames_{split}/{label}/"
    tags_dir = dataset_path + f"tags_{split}/{label}/"
    logreg_dir = join(dataset_path, 'logreg', label)
    os.makedirs(logreg_dir, exist_ok=True)
    os.makedirs(tags_dir, exist_ok=True)

    videos = os.listdir(frames_dir)
    videos.sort()

    logreg = None
    logreg_path = join(logreg_dir, 'logreg.joblib')
    if os.path.isfile(logreg_path):
        logreg = load(logreg_path)

    app.run(debug=True)

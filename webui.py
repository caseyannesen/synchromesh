from flask import Flask, render_template, url_for, jsonify
from scripts.nitb.nitbman import NITB

nitb = NITB()
app = Flask(__name__, template_folder='./templates')

@app.route('/')
def hello_world():
    return render_template('index.html')



@app.route('/api/subscribers')
def subscribers():
    return jsonify(nitb.subscribers)


dapp = app

if __name__ == '__main__':
    app.run(debug=True, port=8000)
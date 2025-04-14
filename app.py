from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello from GitHub on GCP!"

if __name__ == '__main__':
    app.run(host='34.44.99.98', port=5000)

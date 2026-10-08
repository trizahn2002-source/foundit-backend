from flask import jsonify
from config import app
import models  # loads the tables so migrations can find them


@app.route("/api")
def index():
    return jsonify({"message": "FoundIt API is running"})


if __name__ == "__main__":
    app.run(port=5555, debug=True)
from flask import jsonify
from config import app
import models  # loads the tables so migrations can find them

from matches import matches_bp
from dashboard import dashboard_bp

app.register_blueprint(matches_bp)
app.register_blueprint(dashboard_bp)

import item_routes 

@app.route("/api")
def index():
    return jsonify({"message": "FoundIt API is running"})


if __name__ == "__main__":
    app.run(port=5555, debug=True)
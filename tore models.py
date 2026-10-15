[1mdiff --git a/app.py b/app.py[m
[1mindex 735364f..71e3e69 100644[m
[1m--- a/app.py[m
[1m+++ b/app.py[m
[36m@@ -1,7 +1,7 @@[m
 from flask import jsonify[m
 from config import app[m
 import models  # loads the tables so migrations can find them[m
[31m-[m
[32m+[m[32mimport item_routes[m[41m [m
 [m
 @app.route("/api")[m
 def index():[m

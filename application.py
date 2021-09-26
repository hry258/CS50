import os
from functools import wraps
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response
    
# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure upload files process
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp'])
app.config['UPLOAD_FOLDER'] = "/static/user_photos/a"

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///project.db")

# sessions and login
def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Invalid username or password!")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")
    

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirmation")
        
        usernames = db.execute("SELECT username FROM users;")
        for row in usernames:
            if row["username"] == username:
                flash("Username is not available.")
                return redirect("/register")
        
        hash_password = generate_password_hash(password)
        db.execute("INSERT INTO users(username, hash) VALUES(?, ?);", username, hash_password)
        user_id = db.execute("SELECT id FROM users WHERE username = ?;", username)
        session["user_id"] = user_id
        
        return redirect("/login")
    else:
        return render_template("register.html")
        

@app.errorhandler(404)
def page_not_found(e):
    return redirect('/404')
    
@app.route("/404")
def error():
    return render_template("404.html")


@app.route("/")
@login_required
def index():
    data = db.execute("SELECT * FROM photos WHERE user_id = ?;", session["user_id"])
    return render_template("index.html", data=data)


@app.route("/photos")
@login_required
def photos():
    data = db.execute("SELECT * FROM photos WHERE user_id = ?", session["user_id"])
    return render_template("photos.html", data=data)


@app.route("/profile")
@login_required
def profile():
    data = db.execute("SELECT * FROM users WHERE id = ?;", session["user_id"])
    return render_template("profile.html", data=data[0])
           

@app.route("/upload", methods=["POST", "GET"])
@login_required
def upload():
    if request.method == "POST":
        file  = request.files["file"]
        title = request.form.get("title")
        if request.form.get("description"):
            description = request.form.get("description")
        else:
            description = ""
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            folder = session["user_id"]
            if not os.path.isdir(f"/home/ubuntu/project/static/user_photos/{folder}"):
                os.mkdir(f"/home/ubuntu/project/static/user_photos/{folder}")
            
            path = f"/home/ubuntu/project/static/user_photos/{folder}/{filename}"
            db.execute("INSERT INTO photos(user_id, path, title, description) values(?, ?, ?, ?)", session["user_id"], path.lstrip("/home/ubuntu/project"), title, description)
                
            file.save(path)
        
        return redirect("/photos")
    else:
        return render_template("upload.html")
        

@app.route("/delete/<user_id>/<path>")
@login_required
def delete(user_id, path):
    folder = session["user_id"]
    path = f"static/user_photos/{folder}/{path}"
    
    try:
        os.remove(path)
        db.execute("DELETE FROM photos WHERE user_id = ? AND path = ?;", session["user_id"], path)
    except:
        return redirect("/404")
    
    return redirect("/photos")
    
    
@app.route("/edit_photo/<user_id>/<path>", methods=["POST", "GET"])
@login_required
def edit_photo(user_id, path):
    global pathx 
    pathx = path
    return redirect("/edit")
        

@app.route("/edit", methods=["POST", "GET"])
@login_required
def edit():
    global pathx
    path = pathx
    if request.method == "POST":
        try:
            description = request.form.get("description")
        except:
            description = ""
        title = request.form.get("title")
        folder = session["user_id"]
        path = f"static/user_photos/{folder}/{path}"
        db.execute("UPDATE photos SET title = ? WHERE user_id = ? AND path = ?", title, session["user_id"], path)
        db.execute("UPDATE photos SET description = ? WHERE user_id = ? AND path = ?", description, session["user_id"], path)
        return redirect("/photos")
    else:
        folder = session["user_id"]
        path = f"static/user_photos/{folder}/{path}"
        
        photo = db.execute("SELECT * FROM photos WHERE user_id = ? AND path = ?;", session["user_id"], path)
        if len(photo) != 1:
            return redirect("/404")
          
        return render_template("edit_photo.html", photo=photo[0])


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return render_template("error.html", message=e)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
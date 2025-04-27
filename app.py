from flask import Flask, render_template, redirect, request, session, g
from utils import *
from os import urandom, path, makedirs, remove
from functools import wraps

if not database_found():
    create_database()

app = Flask(__name__)
secret_key = urandom(24).hex()
app.secret_key = secret_key
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["UPLOAD_FOLDER"] = "static/analysis-images"
makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("id", None) is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


@app.before_request
def set_language_and_mode():
    g.id = session.get("id", None)
    g.user = session.get("user", None)
    g.lang = session.get("lang", initial_lang)
    g.mode = session.get("mode", initial_display_mode)


initial_display_mode = "light"
toggle_display_mode = {
    "light": "dark",
    "dark": "light"
}


initial_lang = "en"
toggle_lang = {
    "en": "ar",
    "ar": "en"
}


@app.route("/display")
def display():
    old_mode = g.mode
    new_mode = toggle_display_mode[old_mode]
    session.pop("mode", None)
    session["mode"] = new_mode
    return redirect(request.referrer or "/")


@app.route("/language")
def language():
    old_lang = g.lang
    new_lang = toggle_lang[old_lang]
    session.pop("lang", None)
    session["lang"] = new_lang
    return redirect(request.referrer or "/")


# Routes
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", mode=g.mode, lang=g.lang, data=login_data[g.lang])
    
    email = request.form.get("email").lower()
    password = request.form.get("password")

    if not email or not password or not validate_email(email) or not validate_password(password):
        return redirect("/")
    
    user = get_user(email)

    if user is None or not check_pass(password, user["pass_hash"]):
        error = {
            "en": "Wrong email or password",
            "ar": "البريد الإلكتروني أو كلمة المرور خطأ"
        }
        return render_template("login.html", mode=g.mode, lang=g.lang, data=login_data[g.lang], error=error[g.lang])
    
    session["id"] = user["id"]
    session["user"] = user
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", mode=g.mode, lang=g.lang, data=register_data[g.lang])
    
    first_name = request.form.get("first_name").capitalize()
    last_name = request.form.get("last_name").capitalize()
    email = request.form.get("email").lower()
    password = request.form.get("password")

    if (not first_name or not last_name or not email or not password
        or not validate_name(first_name) or not validate_name(last_name)
        or not validate_email(email) or not validate_password(password)):
        return redirect("/")
    
    insert_status = insert_user(email, first_name, last_name, hash_pass(password))
    
    if not insert_status:
        error = {
            "en": "Email is already in use",
            "ar": "البريد الإلكتروني مستعمل"
        }
        return render_template("register.html", mode=g.mode, lang=g.lang, data=register_data[g.lang], error=error[g.lang])
    
    success = {
        "en": "Account was created successfully",
        "ar": "تم إنشاء الحساب بنجاح"
    }
    return render_template("register.html", mode=g.mode, lang=g.lang, data=register_data[g.lang], success=success[g.lang])


@app.route("/logout")
@login_required
def logout():
    session.pop("id", None)
    session.pop("user", None)
    return redirect("/login")


@app.route("/")
@login_required
def index():
    return render_template("index.html", mode=g.mode, lang=g.lang, navbar=base_navbar[g.lang], data=index_data(g.user["first_name"])[g.lang])


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        return render_template("upload.html", mode=g.mode, lang=g.lang, navbar=base_navbar[g.lang], data=upload_data[g.lang])
    
    analysis_count = len(get_user_analysis(g.id))

    file = request.files.get("analysis-image", None)

    if file is None:
        return redirect("/")

    file_extension = path.splitext(file.filename)[1]
    file_extension = str(file_extension).lower()

    if file_extension not in [".png", ".jpg", ".jpeg"]:
        return redirect("/")
    
    file.filename = f"{g.id}-{analysis_count + 1}{file_extension}"
    file_path = path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    insert_status = insert_analysis(g.id, file.filename, analyze_file(file_path))

    if not insert_status:
        remove(path.join(app.config["UPLOAD_FOLDER"], file.filename))
        return redirect("/")
    
    return redirect("/history")


@app.route("/history", methods=["GET", "POST"])
@login_required
def history():
    if request.method == "GET":
        return render_template("history.html", mode=g.mode, lang=g.lang, navbar=base_navbar[g.lang], data=history_data(get_user_analysis(g.id))[g.lang])
    
    id = int(request.form.get("id"))

    delete_status = delete_analysis(id)

    if not delete_status:
        error = {
            "en": "Unable to delete the analysis",
            "ar": "غير قادر على حذف التحليل"
        }
        return render_template("history.html", mode=g.mode, lang=g.lang, navbar=base_navbar[g.lang], data=history_data(get_user_analysis(g.id))[g.lang], error=error[g.lang])
    
    for file_extension in [".png", ".jpg", ".jpeg"]:
        try:
            remove(path.join(app.config["UPLOAD_FOLDER"], f"{g.id}-{id}{file_extension}"))
        except:
            pass
    
    success = {
        "en": "Analysis was successfully deleted",
        "ar": "تم حذف التحليل بنجاح"
    }
    return render_template("history.html", mode=g.mode, lang=g.lang, navbar=base_navbar[g.lang], data=history_data(get_user_analysis(g.id))[g.lang], success=success[g.lang])


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "GET":
        return render_template("account.html", mode=g.mode, lang=g.lang, data=account_data[g.lang], user=g.user)
    
    first_name = request.form.get("first_name").capitalize()
    last_name = request.form.get("last_name").capitalize()
    email = request.form.get("email").lower()
    password = request.form.get("password")
    pass_hash = hash_pass(password)

    if (not first_name or not last_name or not email or not password
        or not validate_name(first_name) or not validate_name(last_name)
        or not validate_email(email) or not validate_password(password)):
        return redirect("/")
    
    update_status = update_user(g.id, email, first_name, last_name, pass_hash)

    if not update_status:
        error = {
            "en": "Email is already in use",
            "ar": "البريد الإلكتروني مستعمل"
        }
        return render_template("account.html", mode=g.mode, lang=g.lang, data=account_data[g.lang], user=g.user, error=error[g.lang])
    
    success = {
        "en": "Account was successfully updated",
        "ar": "تم تحديث الحساب بنجاح"
    }
    session["user"] = get_user(email)
    return render_template("account.html", mode=g.mode, lang=g.lang, data=account_data[g.lang], user=session.get("user", g.user), success=success[g.lang])


@app.route("/analysis", methods=["GET", "POST"])
@login_required
def analysis():
    if request.method == "GET":
        return redirect("/history")

    id = int(request.form.get("id"))

    analysis = get_analysis(id)
    
    if analysis["disease"] is None:
        disease = {
            "en": {
                "name": "Not infected",
            },
            "ar": {
                "name": "غير مصاب",
            }
        }

    elif analysis["disease"] == "unknown":
        disease = {
            "en": {
                "name": "Unknown",
            },
            "ar": {
                "name": "غير معروف",
            }
        }

    else:
        disease_db = get_disease(analysis["disease"])
        disease = {
            "en": {
                "name": disease_db["name"],
                "description": disease_db["description"],
                "treatment": disease_db["treatment"]
            },
            "ar": {
                "name": disease_db["name_ar"],
                "description": disease_db["description_ar"],
                "treatment": disease_db["treatment_ar"]
            }
        }

    file_path = path.join('../static/analysis-images', f'{analysis["file_name"]}')

    return render_template("analysis.html", mode=g.mode, lang=g.lang, 
                           navbar=base_navbar[g.lang], disease=disease[g.lang],
                           date_taken=analysis["date_taken"], time_taken=analysis["time_taken"],
                           image_path=file_path)


@app.route("/camera")
@login_required
def camera():
    return render_template("camera.html", mode=g.mode, lang=g.lang,
                           navbar=base_navbar[g.lang])

# App Runner
if __name__=="__main__":
    app.run(debug=True)
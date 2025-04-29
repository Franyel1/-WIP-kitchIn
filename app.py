#!/usr/bin/env python3

import os
import datetime
import flask_login
import pymongo
from bson.objectid import ObjectId
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv, dotenv_values
from flask_login import login_required, current_user
import random

load_dotenv()  # Load environment variables

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default_secret_key")
config = dotenv_values()
app.config.from_mapping(config)

# Initialize MongoDB connection
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DBNAME")]

app.db = db

# Initialize Flask-Login
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# User model for authentication
class User(flask_login.UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"]) 
        self.email = user_data["email"]
        self.username = user_data["username"]
        self.password = user_data["password"]
        self.households = []
    @staticmethod
    def find_by_username(username):
        """Find user by username in MongoDB."""
        user_data = db.loginInfo.find_one({"username": username})
        return User(user_data) if user_data else None
    @staticmethod
    def find_by_email(email):
        """Find user by email in MongoDB."""
        user_data = db.loginInfo.find_one({"email": email})
        return User(user_data) if user_data else None
    @staticmethod
    def find_by_id(user_id):
        """Find user by ID in MongoDB."""
        user_data = db.loginInfo.find_one({"_id": ObjectId(user_id)})
        return User(user_data) if user_data else None

    @staticmethod
    def create_user(email, username, password):
        """Create a new user in MongoDB."""
        if db.loginInfo.find_one({"username": username}):
            return False  # Username already exists
        
        if db.loginInfo.find_one({"email": email}):
            return False  # Email already exists
        
        hashed_password = generate_password_hash(password) 
        db.loginInfo.insert_one({
            "email": email,
            "username": username,
            "password": hashed_password,
            "households": []
        })
        return True

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.find_by_id(user_id)


@app.route("/")
def index():
    return redirect(url_for("register"))


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None 
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirmPassword"]

        if password != confirm_password:
            error = "Passwords do not match."
        elif User.find_by_email(email):
            error = "Email is already registered."
        elif User.find_by_username(username):
            error = "Username is already taken."
        else:
            if User.create_user(email, username, password):
                return redirect(url_for("login"))
            else:
                error = "An unexpected error occurred during registration."

    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None  
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.find_by_email(email)

        if user and check_password_hash(user.password, password):  
            flask_login.login_user(user)
            return redirect(url_for("home"))
        else:
            error = "Invalid email or password."

    return render_template("login.html", error=error)


@app.route("/home")
@flask_login.login_required
def home():
    error_code = request.args.get('error')  
    if error_code == '999':
        error = "You are already a member of this household."
    elif error_code == '111':
        error = "Invalid household code. Please try again."
    else: 
        error = None
    user = db.loginInfo.find_one({"_id": ObjectId(current_user.id)})
    names = user.get("households", [])
    docs = db.householdData.find({"name": {"$in": names}})
    return render_template("home.html", user=user, households=docs, error=error)

@app.route("/create-household", methods = ['POST'])
@flask_login.login_required
def create_household():
    if request.method == "POST":
        name = request.form['name']
        #color = request.form['color']
        code = generate_code()
        while db.householdData.find_one({'code':code}):
            code = generate_code()
        members = [flask_login.current_user.username]
        grocery = []
        pantry = []
        requests = []
        doc = {'name': name, 'code':code, 'members':members, 'grocery':grocery, 'pantry':pantry, 'requests':requests}
        db.householdData.insert_one(doc)
        user = User.find_by_username(flask_login.current_user.username)
        user.households.append(name)
        db.loginInfo.update_one(
            {"_id": ObjectId(user.id)},
            {"$push": {"households": name}}
        )
        return redirect("/home")

@app.route("/leave-household/<household_id>", methods=["POST"])
@flask_login.login_required
def leave_household(household_id):
    household_id = ObjectId(household_id)
    user = db.loginInfo.find_one({"_id": ObjectId(current_user.id)})
    username = user["username"]

    db.householdData.update_one(
        {"_id": household_id},
        {"$pull": {"members": username}}
    )

    household = db.householdData.find_one({"_id": household_id})
    if household:
        db.loginInfo.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$pull": {"households": household["name"]}}
        )

    return redirect(url_for("home"))
            
def generate_code():
    letters = 'QWERTYUIOPASDFGHJKLZXCVBNM1234567890'
    return ''.join(random.choices(letters,k=4))
    
@app.route("/join-household", methods=["GET", "POST"])
@flask_login.login_required
def join_household():
    error = None
    if request.method == "POST":
        code = request.form['code'].strip().upper()
        household = db.householdData.find_one({'code': code})
        username = flask_login.current_user.username
        user = User.find_by_username(username)

        if household:
            if username not in household.get('members', []):
                db.householdData.update_one(
                    {"_id": household["_id"]},
                    {"$push": {"members": username}}
                )
                db.loginInfo.update_one(
                    {"_id": ObjectId(user.id)},
                    {"$push": {"households": household["name"]}}
                )
                return redirect(url_for("home"))
            else:
                return redirect(url_for("home", error='999'))
        else:
            return redirect(url_for("home", error='111'))

@app.route("/logout")
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect(url_for("login"))

@app.route("/household/<household_id>")
@flask_login.login_required
def household(household_id):
    house_id = ObjectId(household_id)
    doc = db.householdData.find_one({"_id":house_id})
    grocery_ids = doc.get("grocery",[])
    grocery_list = list(db.groceryData.find({"_id":{"$in":grocery_ids}}))
    pantry_ids = doc.get("pantry",[])
    pantry_list = list(db.pantryData.find({"_id":{"$in":pantry_ids}}))
    request_ids = doc.get("requests",[])
    request_list = list(db.requestData.find({"_id":{"$in":request_ids}}))
    username = flask_login.current_user.username
    user = User.find_by_username(username)
    return render_template("household.html",household = doc, groceryList = grocery_list, pantryList = pantry_list, current_user_id = user.id, requestList = request_list)    

@app.route('/requests/<household_id>')
@flask_login.login_required
def requests(household_id):
    house_id = ObjectId(household_id)
    doc = db.householdData.find_one({"_id": house_id})
    request_ids = doc.get("requests", [])
    request_list = list(db.requestData.find({"_id": {"$in": request_ids}}))
    pantry_ids = doc.get("pantry",[])
    pantry_list = list(db.pantryData.find({"_id":{"$in":pantry_ids}}))

    username = flask_login.current_user.username
    user = User.find_by_username(username)
    return render_template("requests.html", household=doc,current_user_id = user.id, requestList = request_list, pantryList=pantry_list)                          

@app.route("/add-grocery/<household_id>", methods = ["POST"])
@flask_login.login_required
def add_grocery(household_id):
    if request.method == "POST":
        name = request.form['name']
        note = request.form['note']
        username = flask_login.current_user.username
        user = User.find_by_username(username)
        requester_id = user.id
        requester = username
        grocery = db.groceryData.insert_one({"name":name,"note":note, "requester_id": requester_id, 'requester':requester, "purchased":False, "purchased_by_id": "", "purchased_by_user": "", "price":0})
        grocery_id = grocery.inserted_id
        house_id = ObjectId(household_id)
        db.householdData.update_one({"_id":house_id},{"$push":{"grocery":grocery_id}})
        return redirect(url_for('household',household_id=household_id))

@app.route("/add-pantry/<household_id>", methods = ["POST"])
@flask_login.login_required
def add_pantry(household_id):
    if request.method == "POST":
        name = request.form['name']
        quantity = request.form['quantity']
        exp_date = request.form['expiration']
        username = flask_login.current_user.username
        user = User.find_by_username(username)
        owner_id = user.id
        owner = username
        pantry = db.pantryData.insert_one({'name':name,'quantity':quantity,'exp_date':exp_date,'owner_id':owner_id, 'owner':owner, 'requests':[]})
        pantry_id = pantry.inserted_id
        house_id = ObjectId(household_id)
        db.householdData.update_one({"_id":house_id},{"$push":{"pantry":pantry_id}})
        return redirect(url_for('household',household_id=household_id))

@app.route("/edit-grocery/<household_id>/<grocery_id>", methods=["POST"])
@flask_login.login_required
def edit_grocery(household_id, grocery_id):
    if request.method == "POST":
        grocery_id = ObjectId(grocery_id)
        house_id = ObjectId(household_id)
        name = request.form['name']
        note = request.form['note']
        db.groceryData.update_one({"_id":ObjectId(grocery_id)},{"$set":{"name":name,"note":note}})
        return redirect(url_for('household',household_id=household_id))

@app.route("/edit-pantry/<household_id>/<pantry_id>", methods=["POST"])
@flask_login.login_required
def edit_pantry(household_id, pantry_id):
    if request.method == "POST":
        pantry_id = ObjectId(pantry_id)
        house_id = ObjectId(household_id)
        name = request.form['name']
        quantity = request.form['quantity']
        exp_date = request.form['expiration']
        db.pantryData.update_one({"_id":ObjectId(pantry_id)},{"$set":{"name":name,"quantity":quantity,"exp_date":exp_date}})
        return redirect(url_for('household',household_id=household_id))

@app.route("/delete-grocery/<household_id>/<grocery_id>", methods=["POST"])
@flask_login.login_required
def delete_grocery(household_id, grocery_id):
    if request.method == "POST":
        grocery_id = ObjectId(grocery_id)
        house_id = ObjectId(household_id)
        db.householdData.update_one({"_id":house_id},{"$pull":{"grocery":grocery_id}})
        db.groceryData.delete_one({'_id':grocery_id})
        return redirect(url_for('household',household_id=household_id))

@app.route("/delete-pantry/<household_id>/<pantry_id>", methods=["POST"])
@flask_login.login_required
def delete_pantry(household_id, pantry_id):
    if request.method == "POST":
        pantry_id = ObjectId(pantry_id)
        house_id = ObjectId(household_id)
        db.householdData.update_one({"_id":house_id},{"$pull":{"pantry":pantry_id}})
        db.pantryData.delete_one({'_id':pantry_id})
        return redirect(url_for('household',household_id=household_id))

@app.route("/create-request/<household_id>/<pantry_id>", methods=['POST'])
@flask_login.login_required
def create_request(household_id, pantry_id):
    if request.method == "POST":
        pantry_id = ObjectId(pantry_id)
        house_id = ObjectId(household_id)
        amount = request.form['amount']
        note = request.form['note']
        user = User.find_by_username(flask_login.current_user.username)
        requester_id = user.id
        requester_name = user.username
        pantry_item = db.pantryData.find_one({"_id": pantry_id})
        if not pantry_item:
            flash("Pantry item not found", "danger")
            return redirect(url_for("household", household_id=household_id))

        item_name = pantry_item.get("name")
        owner_id = pantry_item.get("owner_id")
        owner_name = pantry_item.get("owner")

        request_doc = db.requestData.insert_one({
            'item_id': pantry_id,
            'household_id': house_id,
            'amount': amount,
            'note': note,
            'requester_id': requester_id,
            'requester_name': requester_name,
            'item_name': item_name,
            'owner_id': owner_id,
            'owner_name': owner_name,
            "status": "pending"
        })

        request_id = request_doc.inserted_id
        db.householdData.update_one({"_id": house_id}, {"$push": {"requests": request_id}})
        db.pantryData.update_one({"_id": pantry_id}, {"$push": {"requests": request_id}})

        return redirect(url_for('household', household_id=household_id))
    
@app.route("/delete-request/<household_id>/<request_id>", methods=["POST"])
@flask_login.login_required
def delete_request(household_id, request_id):
    request_obj = db.requestData.find_one({"_id": ObjectId(request_id)})

    if not request_obj:
        flash("Request not found.", "danger")
        return redirect(url_for("requests", household_id=household_id))

    db.householdData.update_one(
        {"_id": ObjectId(household_id)},
        {"$pull": {"requests": ObjectId(request_id)}}
    )

    db.pantryData.update_one(
        {"_id": request_obj["item_id"]},
        {"$pull": {"requests": ObjectId(request_id)}}
    )

    db.requestData.delete_one({"_id": ObjectId(request_id)})

    return redirect(url_for("requests", household_id=household_id))

@app.route("/respond-request/<household_id>/<request_id>", methods=["POST"])
@flask_login.login_required
def respond_request(household_id, request_id):
    action = request.form["action"]
    if action not in ["accept", "deny"]:
        flash("Invalid action", "danger")
        return redirect(url_for("requests", household_id=household_id))

    status = "accepted" if action == "accept" else "denied"
    db.requestData.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": status}}
    )
    flash(f"Request {status}.", "success")
    return redirect(url_for("requests", household_id=household_id))
        
@app.route("/grocery-purchase/<household_id>/<grocery_id>",methods=["POST"])
@flask_login.login_required
def grocery_purchase(household_id, grocery_id):
    if request.method == "POST":
        grocery_id = ObjectId(grocery_id)
        house_id = ObjectId(household_id)
        price = request.form['price']
        username = flask_login.current_user.username
        user = User.find_by_username(username)
        db.groceryData.update_one({'_id':grocery_id},{"$set":{"purchased":True,"purchased_by_id":user.id,"purchased_by_user":username,"price":price}})
        grocery = db.groceryData.find_one({"_id":grocery_id})
        name = grocery.get("name")
        quantity = request.form['quantity']
        exp_date = request.form['expiration']
        requester_id = grocery.get("requester_id")
        requester = grocery.get("requester")
        pantry_item = db.pantryData.insert_one({'name':name,'quantity':quantity,'exp_date':exp_date,'owner_id':requester_id, 'owner':requester, 'requests':[]})
        db.householdData.update_one({"_id":house_id}, {'$push':{"pantry":pantry_item.inserted_id}})
        return redirect(url_for('household',household_id=household_id))

# Run the app
if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")
    app.run(debug=True, host="0.0.0.0", port=5000)


###############################HOUSEHOLD###########################
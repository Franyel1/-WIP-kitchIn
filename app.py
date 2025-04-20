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
    
    def get_friends(self):
        """Retrieve the user's friends as User objects."""
        friend_ids = [ObjectId(fid) for fid in self.friends]
        friends_data = db.loginInfo.find({"_id": {"$in": friend_ids}})
        return [User(friend) for friend in friends_data]

    def add_friend(self, friend_id):
        """Add a friend using ObjectId reference."""
        friend_id = ObjectId(friend_id)
        if friend_id not in self.friends:
            db.loginInfo.update_one(
                {"_id": ObjectId(self.id)},
                {"$push": {"friends": friend_id}}
            )
            return True
        return False

    def remove_friend(self, friend_id):
        """Remove a friend using ObjectId reference."""
        friend_id = ObjectId(friend_id)
        if friend_id in self.friends:
            db.loginInfo.update_one(
                {"_id": ObjectId(self.id)},
                {"$pull": {"friends": friend_id}}
            )
            return True
        return False


# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.find_by_id(user_id)


@app.route("/")
def index():
    return redirect(url_for("register"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]

        if User.create_user(email, username, password):
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Username already exists. Please try again.", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.find_by_email(email)

        if user and check_password_hash(user.password, password):  
            flask_login.login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("home"))

        flash("Invalid credentials", "danger")

    return render_template("login.html")


@app.route("/home")
@flask_login.login_required
def home():
    user = db.loginInfo.find_one({"_id": ObjectId(current_user.id)})
    names = user.get("households", [])
    docs = db.householdData.find({"name": {"$in": names}})
    return render_template("home.html", user = user, households = docs)

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
            
def generate_code():
    letters = 'QWERTYUIOPASDFGHJKLZXCVBNM1234567890'
    return ''.join(random.choices(letters,k=4))
    
@app.route("/join-household", methods=['POST'])
@flask_login.login_required
def join_household():
    if request.method == "POST":
        code = request.form['code']
    household = db.householdData.find_one({'code':code})
    username = flask_login.current_user.username
    user = User.find_by_username(username)
    if household:
        if username not in household.get('members', []):
            db.householdData.update_one(
                {"_id":household["_id"]},
                {"$push":{"members":username}}
            )
            db.loginInfo.update_one(
                {"_id": ObjectId(user.id)},
                {"$push": {"households": household["name"]}}
            )
        else:
            print('error')
    else:
        print('error')
    return redirect("/home")


@app.route("/logout")
@flask_login.login_required
def logout():
    flask_login.logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for("login"))


@app.route("/add", methods=["GET","POST"])
@flask_login.login_required
def add():
    if request.method == "POST":
        doc = {}
        for item in request.form:
            doc[item] = request.form[item]
        doc['user_id'] = flask_login.current_user.username
        db.restaurantData.insert_one(doc)
        return redirect("/home")
    return render_template("add.html")

@app.route("/household/<household_id>")
@flask_login.login_required
def household(household_id):
    house_id = ObjectId(household_id)
    doc = db.householdData.find_one({"_id":house_id})
    return render_template("household.html",household = doc)                              

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
        grocery = db.groceryData.insert_one({'name':name,'note':note, 'requester_id': requester_id, 'requester':requester})
        house_id = ObjectId(household_id)
        db.householdData.update_one({"_id":house_id},{"$push":{"grocery":grocery}})
        return redirect(url_for('household',household_id=house_id))

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
        pantry = db.pantryData.insert_one({'name':name,'quantity':quantity,'exp_date':exp_date,'owner_id':owner_id, 'owner':owner})
        house_id = ObjectId(household_id)
        db.householdData.update_one({"_id":house_id},{"$push":{"pantry":pantry}})
        return redirect(url_for('household',household_id=house_id))

@app.route("/edit-grocery/<household_id>/<grocery_id>", methods=["POST"])
@flask_login.login_required
def edit_grocery(household_id, grocery_id):
    if request.method == "POST":
        grocery_id = ObjectId(grocery_id)
        house_id = ObjectId(household_id)
        name = request.form['name']
        note = request.form['note']
        db.groceryData.update_one({"_id":ObjectId(grocery_id)},{"$set":{"name":name,"note":note, "purchased":False, "purchased_by_id": "", "purchased_by_user": "", "price":0}})
        return redirect(url_for('household',household_id=house_id))

@app.route("/edit-pantry/<houeshold_id>/<pantry_id>", methods=["POST"])
@flask_login.login_required
def edit_pantry(household_id, pantry_id):
    if request.method == "POST":
        pantry_id = ObjectId(pantry_id)
        house_id = ObjectId(household_id)
        name = request.form['name']
        quantity = request.form['quantity']
        exp_date = request.form['expiration']
        db.pantryData.update_one({"_id":ObjectId(pantry_id)},{"$set":{"name":name,"quantity":quantity,"exp_date":exp_date}})
        return redirect(url_for('household',household_id=house_id))

@app.route("/delete-grocery/<household_id>/<grocery_id>", methods=["POST"])
@flask_login.login_required
def delete_grocery(household_id, grocery_id):
    if request.method == "POST":
        grocery_id = ObjectId(grocery_id)
        house_id = ObjectId(household_id)
        db.householdData.update_one({"_id":house_id},{"$pull":{"grocery":grocery_id}})
        db.groceryData.delete_one({'_id':grocery_id})
        return redirect(url_for('household',household_id=house_id))

@app.route("/delete-pantry/<household_id>/<pantry_id>", methods=["POST"])
@flask_login.login_required
def delete_pantry(household_id, pantry_id):
    if request.method == "POST":
        pantry_id = ObjectId(pantry_id)
        house_id = ObjectId(household_id)
        db.householdData.update_one({"_id":house_id},{"$pull":{"pantry":pantry_id}})
        db.pantryData.delete_one({'_id':pantry_id})
        return redirect(url_for('household',household_id=house_id))

@app.route("/create-request/<household_id>/<pantry_id>", methods=['POST'])
@flask_login.login_required
def create_request(household_id, pantry_id):
    if request.method == "POST":
        pantry_id = ObjectId(pantry_id)
        house_id = ObjectId(household_id)
        
@app.route("/grocery-purchase/<household_id>/<grocery_id>",methods=["POST"])
@flask_login.login_required
def grocery_purchase(household_id, grocery_id):
    if request.method == "POST":
        grocery_id = ObjectId(grocery_id)
        house_id = ObjectId(household_id)
        purchased = True
        price = request.form['price']
        username = flask_login.current_user.username
        user = User.find_by_username(username)
        db.groceryData.update_one({'_id':grocery_id},{"$set":{"purchased":True,"purchased_by_id":user.id,"purchased_by_user":username,"price":price}})
        grocery = db.groceryData.find_one({"_id":grocery_id})
        name = grocery.get("name")
        quantity = request.form['quantity']
        exp_date = request.form['expiration']
        db.pantryData.insert_one({"name":name,"quantity":quantity,"exp_date":exp_date})
        return redirect(url_for('household',household_id=house_id))

@app.route("/edit/<rest_id>",methods=["GET","POST"])
def edit(rest_id):
    rest_id = ObjectId(rest_id)
    if request.method=="GET":
        restaurant = db.restaurantData.find_one({'_id':rest_id})
        print(restaurant)
        return render_template("edit.html",restaurant=restaurant)
    if request.method=="POST":
        doc = {item: request.form[item] for item in request.form}
        doc['user_id'] = flask_login.current_user.username
        db.restaurantData.update_one({'_id':rest_id},{"$set":doc})
        return redirect("/home")

@app.route("/delete/<rest_id>")
def delete(rest_id):
    rest_id = ObjectId(rest_id)
    db.restaurantData.delete_one({'_id':rest_id})
    return redirect("/home")



####################################################################################
################################# PROFILE SECTION ##################################
####################################################################################

@app.route("/profile/<friend_id>", methods=["GET"])
def profile(friend_id):
    if request.method=="GET":
        friend_id = ObjectId(friend_id)
        username = db.loginInfo.find_one({"_id":friend_id})['username']
        restaurants = db.restaurantData.find({"user_id":username})
        return render_template("profile.html",friendName=username,restaurants=restaurants)


# Run the app
if __name__ == "__main__":
    FLASK_PORT = os.getenv("FLASK_PORT", "5000")
    FLASK_ENV = os.getenv("FLASK_ENV")
    print(f"FLASK_ENV: {FLASK_ENV}, FLASK_PORT: {FLASK_PORT}")
    app.run(debug=True, host="0.0.0.0", port=5000)


###############################HOUSEHOLD###########################


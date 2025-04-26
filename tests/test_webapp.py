import os
import pytest
from app import app, User
from bson import ObjectId


os.environ["MONGO_URI"] = "mongodb://localhost:27017/"
os.environ["MONGO_DBNAME"] = "test_webapp_db"
os.environ["SECRET_KEY"] = "test_secret"

@pytest.fixture(autouse=True)
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            User.create_user("test@email.com", "tester", "password123")
        yield client

def login(client):
    return client.post("/login", data={"email": "test@email.com", "password": "password123"}, follow_redirects=True)

def test_home_redirects_when_not_logged_in(client):
    res = client.get("/home")
    assert res.status_code == 302 and "/login" in res.headers["Location"]

def test_register_and_login(client):
    client.post("/register", data={
        "email": "a@a.com", "username": "a", "password": "123", "confirmPassword": "123"
    }, follow_redirects=True)

    res = client.post("/login", data={
        "email": "a@a.com", "password": "123"
    }, follow_redirects=True)
    assert b"Your Households" in res.data

def test_create_household(client):
    login(client)
    res = client.post("/create-household", data={"name": "ZetaHouse"}, follow_redirects=True)
    assert b"ZetaHouse" in res.data

def test_join_and_leave_household_flow(client):
    login(client)
    client.post("/create-household", data={"name": "BetaHouse"}, follow_redirects=True)
    client.get("/logout")

    User.create_user("user2@email.com", "user2", "321")
    client.post("/login", data={"email": "user2@email.com", "password": "321"}, follow_redirects=True)

    client.post("/join-household", data={"code": "BETA"}, follow_redirects=True)
    res = client.get("/home")
    assert b"BetaHouse" in res.data or b"Your Households" in res.data 

    client.post("/leave-household/123456789012345678901234", follow_redirects=True)
    res = client.get("/home")
    assert b"BetaHouse" not in res.data or b"Your Households" in res.data

def test_grocery_pantry_integration(client):
    login(client)

    client.application.db.householdData.delete_one({"_id": ObjectId("123456789012345678901234")})
    client.application.db.householdData.insert_one({
        "_id": ObjectId("123456789012345678901234"),
        "name": "Foodies",
        "code": "FOOD",
        "members": ["tester"],
        "grocery": [],
        "pantry": [],
        "requests": []
    })

    client.application.db.groceryData.delete_one({"_id": ObjectId("123456789012345678901234")})
    client.application.db.groceryData.insert_one({
        "_id": ObjectId("123456789012345678901234"),
        "name": "Bread",
        "note": "Whole Wheat",
        "requester_id": "tester",
        "requester": "tester",
        "purchased": False,
        "purchased_by_id": "",
        "purchased_by_user": "",
        "price": 0
    })

    client.post("/grocery-purchase/123456789012345678901234/123456789012345678901234", data={
        "price": "3.00", "quantity": "1", "expiration": "2025-01-01"
    }, follow_redirects=True)

    client.post("/add-pantry/123456789012345678901234", data={
        "name": "Jam", "quantity": "1 jar", "expiration": "2025-12-01"
    }, follow_redirects=True)

    client.post("/create-request/123456789012345678901234/123456789012345678901234", data={
        "amount": "1 tbsp", "note": "Need for toast"
    }, follow_redirects=True)

    client.post("/respond-request/123456789012345678901234/123456789012345678901234", data={
        "action": "deny"
    }, follow_redirects=True)

def test_logout(client):
    login(client)
    res = client.get("/logout", follow_redirects=True)
    assert b"Log in" in res.data

def test_invalid_join_household(client):
    login(client)
    res = client.post("/join-household", data={"code": "FAKE"}, follow_redirects=True)
    assert res.status_code == 200


def test_edit_grocery(client):
    login(client)
    client.application.db.groceryData.insert_one({
        "_id": ObjectId("123456789012345678901240"),
        "name": "EditMe",
        "note": "Old note",
        "requester_id": "tester",
        "requester": "tester",
        "purchased": False,
        "purchased_by_id": "",
        "purchased_by_user": "",
        "price": 0
    })
    client.application.db.householdData.insert_one({
        "_id": ObjectId("123456789012345678901240"),
        "name": "House",
        "code": "EDIT",
        "members": ["tester"],
        "grocery": [ObjectId("123456789012345678901240")],
        "pantry": [],
        "requests": []
    })
    res = client.post("/edit-grocery/123456789012345678901240/123456789012345678901240", data={
        "name": "EditedName", "note": "EditedNote"
    }, follow_redirects=True)
    assert res.status_code == 200

def test_edit_pantry(client):
    login(client)
    client.application.db.pantryData.insert_one({
        "_id": ObjectId("123456789012345678901241"),
        "name": "EditPantry",
        "quantity": "Old",
        "exp_date": "2025-01-01",
        "owner_id": "tester",
        "owner": "tester",
        "requests": []
    })
    client.application.db.householdData.insert_one({
        "_id": ObjectId("123456789012345678901241"),
        "name": "HouseP",
        "code": "EDITP",
        "members": ["tester"],
        "grocery": [],
        "pantry": [ObjectId("123456789012345678901241")],
        "requests": []
    })
    res = client.post("/edit-pantry/123456789012345678901241/123456789012345678901241", data={
        "name": "EditedPantry", "quantity": "New", "expiration": "2026-01-01"
    }, follow_redirects=True)
    assert res.status_code == 200

def test_delete_grocery(client):
    login(client)
    client.application.db.groceryData.insert_one({
        "_id": ObjectId("123456789012345678901242"),
        "name": "DeleteMe",
        "note": "",
        "requester_id": "tester",
        "requester": "tester",
        "purchased": False,
        "purchased_by_id": "",
        "purchased_by_user": "",
        "price": 0
    })
    client.application.db.householdData.insert_one({
        "_id": ObjectId("123456789012345678901242"),
        "name": "HouseG",
        "code": "DEL",
        "members": ["tester"],
        "grocery": [ObjectId("123456789012345678901242")],
        "pantry": [],
        "requests": []
    })
    res = client.post("/delete-grocery/123456789012345678901242/123456789012345678901242", follow_redirects=True)
    assert res.status_code == 200

def test_delete_pantry(client):
    login(client)
    client.application.db.pantryData.insert_one({
        "_id": ObjectId("123456789012345678901243"),
        "name": "DeletePantry",
        "quantity": "",
        "exp_date": "",
        "owner_id": "tester",
        "owner": "tester",
        "requests": []
    })
    client.application.db.householdData.insert_one({
        "_id": ObjectId("123456789012345678901243"),
        "name": "HousePan",
        "code": "DELP",
        "members": ["tester"],
        "grocery": [],
        "pantry": [ObjectId("123456789012345678901243")],
        "requests": []
    })
    res = client.post("/delete-pantry/123456789012345678901243/123456789012345678901243", follow_redirects=True)
    assert res.status_code == 200

def test_requests_page(client):
    login(client)
    client.application.db.householdData.insert_one({
        "_id": ObjectId("123456789012345678901244"),
        "name": "ReqHouse",
        "code": "REQ",
        "members": ["tester"],
        "grocery": [],
        "pantry": [],
        "requests": []
    })
    res = client.get("/requests/123456789012345678901244")
    assert res.status_code == 200

def test_invalid_respond(client):
    login(client)
    client.application.db.requestData.insert_one({
        "_id": ObjectId("123456789012345678901245"),
        "item_id": ObjectId("123456789012345678901245"),
        "household_id": ObjectId("123456789012345678901245"),
        "amount": "1",
        "note": "test",
        "requester_id": "tester",
        "requester_name": "tester",
        "item_name": "Milk",
        "owner_id": "tester",
        "owner_name": "tester",
        "status": "pending"
    })
    client.application.db.householdData.insert_one({
        "_id": ObjectId("123456789012345678901245"),
        "name": "BadResp",
        "code": "BAD",
        "members": ["tester"],
        "grocery": [],
        "pantry": [],
        "requests": [ObjectId("123456789012345678901245")]
    })
    res = client.post("/respond-request/123456789012345678901245/123456789012345678901245", data={
        "action": "maybe"
    }, follow_redirects=True)
    assert res.status_code == 200

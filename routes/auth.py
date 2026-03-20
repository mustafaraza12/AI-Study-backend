from flask import Blueprint, request, jsonify
from pymongo import MongoClient
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import bcrypt
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client    = MongoClient(MONGO_URI)
db        = client["aistudydb"]
users     = db["users"]

auth_bp = Blueprint("auth_routes", __name__)


# ── Register ─────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data     = request.json
        name     = data.get("name", "").strip()
        email    = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400

        if users.find_one({"email": email}):
            return jsonify({"error": "Email already registered"}), 409

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        users.insert_one({
            "name":     name,
            "email":    email,
            "password": hashed,
            "provider": "email",
        })

        token = create_access_token(
            identity=email,
            expires_delta=timedelta(days=7)
        )

        return jsonify({
            "message": "Account created successfully",
            "token":   token,
            "user":    { "name": name, "email": email }
        }), 201

    except Exception as e:
        print("Register Error:", e)
        return jsonify({"error": "Server error"}), 500


# ── Login ────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data     = request.json
        email    = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        user = users.find_one({"email": email})
        if not user:
            return jsonify({"error": "Invalid email or password"}), 401

        if not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
            return jsonify({"error": "Invalid email or password"}), 401

        token = create_access_token(
            identity=email,
            expires_delta=timedelta(days=7)
        )

        return jsonify({
            "message": "Login successful",
            "token":   token,
            "user":    { "name": user.get("name", ""), "email": email }
        }), 200

    except Exception as e:
        print("Login Error:", e)
        return jsonify({"error": "Server error"}), 500


# ── Me (get current user) ────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    try:
        email = get_jwt_identity()
        user  = users.find_one({"email": email}, {"password": 0})
        if not user:
            return jsonify({"error": "User not found"}), 404
        user["_id"] = str(user["_id"])
        return jsonify({"user": user}), 200
    except Exception as e:
        print("Me Error:", e)
        return jsonify({"error": "Server error"}), 500


# ── Google Login ─────────────────────────────────────────────
@auth_bp.route("/google-login", methods=["POST"])
def google_login():
    try:
        print("=== RAW REQUEST ===")
        print("Content-Type:", request.content_type)
        print("Raw data:", request.data)
        print("JSON:", request.json)
        print("Form:", request.form)
        print("===================")
        data = request.json
        print("=== GOOGLE LOGIN ===")
        print("Data received:", data)

        if not data:
            return jsonify({"error": "No data received"}), 400

        # ✅ Get token — NOT email/password
        token = data.get("token")
        print("Token exists:", bool(token))

        if not token:
            return jsonify({"error": "Token is required"}), 400

        # Verify Google token
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        print("Google Client ID loaded:", bool(google_client_id))

        if not google_client_id:
            return jsonify({"error": "Google Client ID not configured"}), 500

        try:
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                google_client_id
            )
            print("Token verified successfully")
        except ValueError as ve:
            print("Token verification failed:", ve)
            return jsonify({"error": f"Invalid Google token: {str(ve)}"}), 401

        email = id_info.get("email", "").lower()
        name  = id_info.get("name", "")
        print("Google user:", email, name)

        if not email:
            return jsonify({"error": "Could not get email from Google"}), 400

        # Check if user exists — if not create one
        user = users.find_one({"email": email})
        if not user:
            print("Creating new Google user:", email)
            users.insert_one({
                "name":     name,
                "email":    email,
                "password": None,
                "provider": "google",
            })
        else:
            print("Existing user found:", email)

        # Create JWT token
        jwt_token = create_access_token(
            identity=email,
            expires_delta=timedelta(days=7)
        )

        print("=== GOOGLE LOGIN SUCCESS ===")

        return jsonify({
            "message": "Google login successful",
            "token":   jwt_token,
            "user":    { "name": name, "email": email }
        }), 200

    except Exception as e:
        print("=== GOOGLE LOGIN ERROR ===")
        print("Error type:", type(e).__name__)
        print("Error:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


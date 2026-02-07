from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import random
import string
import os
app = Flask(__name__)
CORS(app)


DOMAIN = os.getenv("OKTA_DOMAIN", "https://integrator-6652914.okta.com")
TOKEN = os.getenv("OKTA_TOKEN")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")

HEADERS = {
    "Authorization": f"SSWS {TOKEN}",
    "Content-Type": "application/json"
}

# Helper Functions
def generate_username():
    """Generate random username"""
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{rand}@prokodelabs.com"

def generate_password():
    """Generate secure random password"""
    return (
        random.choice(string.ascii_uppercase) +
        random.choice(string.ascii_lowercase) +
        random.choice(string.digits) +
        random.choice("!@#$%") +
        ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    )

# API Endpoints

@app.route('/create-account', methods=['POST'])
def create_account():
    """Create temporary exam account for candidate"""
    try:
        data = request.json
        candidate_email = data.get('candidate_email')
        
        if not candidate_email:
            return jsonify({"error": "Email is required"}), 400
        
        username = generate_username()
        password = generate_password()
        
        # Create user in Okta
        payload = {
            "profile": {
                "login": username,
                "email": candidate_email,  # Candidate's real email for MFA
                "firstName": "Candidate",
                "lastName": "Exam"
            },
            "credentials": {
                "password": {
                    "value": password
                }
            }
        }
        
        response = requests.post(
            f"{DOMAIN}/api/v1/users?activate=true",
            headers=HEADERS,
            json=payload
        )
        
        if response.status_code != 200:
            print("User creation failed:", response.text)
            return jsonify({"error": "Failed to create user"}), 500
        
        user_data = response.json()
        user_id = user_data["id"]
        
        # Assign to admin group
        requests.put(
            f"{DOMAIN}/api/v1/groups/{ADMIN_GROUP_ID}/users/{user_id}",
            headers=HEADERS
        )
        
        print(f"✅ Created exam account: {username} for {candidate_email}")
        
        return jsonify({
            "success": True,
            "username": username,
            "password": password,
            "user_id": user_id,
            "candidate_email": candidate_email
        })
        
    except Exception as e:
        print(f"Error creating account: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/validate', methods=['POST'])
def validate():
    """Validate exam tasks and cleanup account"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        # Validation logic (same as before)
        results = []
        
        # Task 1: Check user Ben Carter
        user_result = check_user(
            "ben.carter@oktacertified.com",
            {
                "firstName": "Ben",
                "lastName": "Carter",
                "department": "Technology",
                "title": "IT Intern"
            }
        )
        results.append({
            "name": "User Creation",
            "status": user_result.get("status", "fail")
        })
        
        # Task 2: Check custom attribute
        attr_result = check_custom_attribute("internId")
        results.append({
            "name": "Custom Attribute",
            "status": attr_result.get("status", "fail")
        })
        
        # Task 3: Check attribute value
        value_result = check_custom_attribute_value(
            "ben.carter@oktacertified.com",
            "internId",
            "INT-2024-07"
        )
        results.append({
            "name": "Attribute Value",
            "status": value_result.get("status", "fail")
        })
        
        # Task 4: Check group
        group_result = check_group("Summer Interns")
        results.append({
            "name": "Group Creation",
            "status": group_result.get("status", "fail")
        })
        
        # Calculate score
        passed = sum(1 for r in results if r["status"] == "pass")
        total = len(results)
        overall_status = "pass" if passed == total else "fail"
        
        # CLEANUP: Delete candidate's temporary account
        if user_id:
            cleanup_result = delete_user(user_id)
            print(f"🧹 Cleanup: {cleanup_result}")
        
        return jsonify({
            "overall_status": overall_status,
            "score": passed,
            "total": total,
            "use_cases": results
        })
        
    except Exception as e:
        print(f"Validation error: {str(e)}")
        return jsonify({
            "error": str(e),
            "overall_status": "fail",
            "score": 0,
            "total": 4
        }), 500

def delete_user(user_id):
    """Deactivate and delete user account"""
    try:
        # Deactivate user first
        deactivate_response = requests.post(
            f"{DOMAIN}/api/v1/users/{user_id}/lifecycle/deactivate",
            headers=HEADERS
        )
        
        if deactivate_response.status_code == 200:
            # Delete user
            delete_response = requests.delete(
                f"{DOMAIN}/api/v1/users/{user_id}",
                headers=HEADERS
            )
            
            if delete_response.status_code == 204:
                return f"User {user_id} deleted successfully"
            else:
                return f"User deactivated but deletion failed: {delete_response.status_code}"
        else:
            return f"Deactivation failed: {deactivate_response.status_code}"
            
    except Exception as e:
        return f"Cleanup error: {str(e)}"

# Validation Functions (same as before)

def check_user(email, expected_profile):
    """Check if user exists with correct profile"""
    try:
        search_url = f"{DOMAIN}/api/v1/users?search=profile.email eq \"{email}\""
        response = requests.get(search_url, headers=HEADERS)
        
        if response.status_code != 200:
            return {"status": "fail"}
        
        users = response.json()
        if not users:
            return {"status": "fail"}
        
        profile = users[0].get("profile", {})
        
        # Check all fields
        all_match = (
            profile.get("firstName") == expected_profile.get("firstName") and
            profile.get("lastName") == expected_profile.get("lastName") and
            profile.get("department") == expected_profile.get("department") and
            profile.get("title") == expected_profile.get("title")
        )
        
        return {"status": "pass" if all_match else "fail"}
    except:
        return {"status": "fail"}

def check_custom_attribute(variable_name):
    """Check if custom attribute exists"""
    try:
        schema_url = f"{DOMAIN}/api/v1/meta/schemas/user/default"
        response = requests.get(schema_url, headers=HEADERS)
        
        if response.status_code != 200:
            return {"status": "fail"}
        
        schema = response.json()
        properties = schema.get("definitions", {}).get("custom", {}).get("properties", {})
        
        exists = variable_name in properties
        return {"status": "pass" if exists else "fail"}
    except:
        return {"status": "fail"}

def check_custom_attribute_value(email, attribute_name, expected_value):
    """Check if custom attribute has correct value"""
    try:
        search_url = f"{DOMAIN}/api/v1/users?search=profile.email eq \"{email}\""
        response = requests.get(search_url, headers=HEADERS)
        
        if response.status_code != 200:
            return {"status": "fail"}
        
        users = response.json()
        if not users:
            return {"status": "fail"}
        
        profile = users[0].get("profile", {})
        actual_value = profile.get(attribute_name)
        
        is_match = str(actual_value) == str(expected_value)
        return {"status": "pass" if is_match else "fail"}
    except:
        return {"status": "fail"}

def check_group(group_name):
    """Check if group exists"""
    try:
        search_url = f"{DOMAIN}/api/v1/groups?q={group_name}"
        response = requests.get(search_url, headers=HEADERS)
        
        if response.status_code != 200:
            return {"status": "fail"}
        
        groups = response.json()
        exists = len(groups) > 0
        return {"status": "pass" if exists else "fail"}
    except:
        return {"status": "fail"}

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Okta Exam Server Starting...")
    print("=" * 50)
    print(f"📍 Okta Tenant: {DOMAIN}")
    print(f"👥 Admin Group ID: {ADMIN_GROUP_ID}")
    print("\n📡 Endpoints:")
    print("   POST /create-account  - Create exam account")
    print("   POST /validate        - Validate & cleanup")
    print("   GET  /health          - Health check")
    print("=" * 50)
    app.run(debug=True, port=5000, host='0.0.0.0')

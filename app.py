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
REQUIRED_TASKS = 6

HEADERS = {
    "Authorization": f"SSWS {TOKEN}",
    "Content-Type": "application/json"
}

# Helper Functions
def missing_config():
    missing = []
    if not TOKEN:
        missing.append("OKTA_TOKEN")
    if not ADMIN_GROUP_ID:
        missing.append("ADMIN_GROUP_ID")
    return missing
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

def okta_get(url, params=None):
    return requests.get(url, headers=HEADERS, params=params)

def okta_post(url, json=None):
    return requests.post(url, headers=HEADERS, json=json)

def okta_put(url, json=None):
    return requests.put(url, headers=HEADERS, json=json)

def okta_delete(url):
@@ -58,50 +66,54 @@ def find_group_by_name(group_name):
            if profile.get("name") == group_name:
                return g
        return None
    except:
        return None

def find_user_by_profile_email(email):
    """Return first matching user object by profile.email, or None"""
    try:
        search_url = f"{DOMAIN}/api/v1/users"
        params = {"search": f'profile.email eq "{email}"'}
        response = okta_get(search_url, params=params)
        if response.status_code != 200:
            return None

        users = response.json() or []
        return users[0] if users else None
    except:
        return None

# API Endpoints
@app.route('/create-account', methods=['POST'])
def create_account():
    """Create temporary exam account for candidate"""
    try:
        missing = missing_config()
        if missing:
            return jsonify({"error": f"Missing required config: {', '.join(missing)}"}), 500

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
@@ -118,50 +130,59 @@ def create_account():

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
        missing = missing_config()
        if missing:
            return jsonify({
                "error": f"Missing required config: {', '.join(missing)}",
                "overall_status": "fail",
                "score": 0,
                "total": REQUIRED_TASKS,
            }), 500

        data = request.json
        user_id = data.get('user_id')

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
@@ -202,51 +223,51 @@ def validate():
            "status": member_result.get("status", "fail")
        })

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
            "total": 6
            "total": REQUIRED_TASKS
        }), 500

def delete_user(user_id):
    """Deactivate and delete user account"""
    try:
        deactivate_response = requests.post(
            f"{DOMAIN}/api/v1/users/{user_id}/lifecycle/deactivate",
            headers=HEADERS
        )

        if deactivate_response.status_code == 200:
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

index.html
index.html
+10
-2

@@ -742,60 +742,68 @@
    }

    /* FIX: wrappers required because HTML uses onchange="updateTask1()" etc. [file:1] */
    function updateTask1() { updateTask(1); }
    function updateTask2() { updateTask(2); }
    function updateTask3() { updateTask(3); }
    function updateTask4() { updateTask(4); }
    function updateTask5() { updateTask(5); }
    function updateTask6() { updateTask(6); }

    async function submitExam() {
      clearInterval(timerInterval);

      const btn = document.getElementById('submitBtn');
      btn.disabled = true;
      btn.innerHTML = 'Validation in progress...';

      try {
        const response = await fetch('https://prokode-exam.onrender.com/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId })
        });

        const data = await response.json();
        if (!response.ok || data.error) {
          alert(data.error || 'Validation error. Contact the system administrator.');
          btn.disabled = false;
          btn.innerHTML = 'Submit Validation Request';
          return;
        }

        const resultCard = document.getElementById('resultCard');
        resultCard.classList.remove('hidden');
        const total = Number.isFinite(data.total) ? data.total : 6;

        if (data.overall_status === 'pass') {
          resultCard.className = 'result-card';
          resultCard.innerHTML = `
            <h2>Validation Result Passed</h2>
            <div class="score">${data.score}/${data.total}</div>
            <div class="score">${data.score}/${total}</div>
            <p>All required checks returned a passing status.</p>
            <p style="margin-top:12px;color:#4b5563;font-size:13px;">
              Temporary account cleanup completed.<br />
              Results will be sent to the provided email address.
            </p>
          `;
        } else {
          resultCard.className = 'result-card fail';
          resultCard.innerHTML = `
            <h2>Validation Result Not Passed</h2>
            <div class="score" style="color:#111827;">${data.score}/${data.total}</div>
            <div class="score" style="color:#111827;">${data.score}/${total}</div>
            <p>One or more checks did not meet the required criteria.</p>
            <p style="margin-top:12px;color:#4b5563;font-size:13px;">
              Temporary account cleanup completed.<br />
              Detailed results will be sent to the provided email address.
            </p>
          `;
        }

        resultCard.scrollIntoView({ behavior: 'smooth' });
      } catch (error) {
        alert('Validation error. Contact the system administrator.');
      }
    }
  </script>
</body>
</html>

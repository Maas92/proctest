# deploy.py

import os
import sys

# Add the project's root directory to the Python path.
# This is essential to find and import the 'main.py' module.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the core deployment function from your main script
from main import deploy_stored_procedures

def deploy():
    """
    This function acts as a wrapper for the main deployment logic.
    """
    print("Starting deployment orchestration...")
    deploy_stored_procedures()
    print("Deployment orchestration finished.")

if __name__ == "__main__":
    deploy()

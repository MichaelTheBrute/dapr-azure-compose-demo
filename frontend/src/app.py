import os
from flask import Flask, render_template, request, jsonify
import requests
import logging
import traceback

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def is_running_in_azure():
    """More reliable method to detect Azure Container Apps environment"""
    # Method 1: Check for environment variables that exist in Container Apps
    azure_env_indicators = [
        'CONTAINER_APP_NAME',       # Set in Container Apps
        'WEBSITES_CONTAINER_START_TIME',  # Set in Container Apps
        'CONTAINER_APP_REVISION'    # Container Apps revision identifier
    ]
    
    for var in azure_env_indicators:
        if os.getenv(var):
            logger.info(f"Azure detected via environment variable: {var}={os.getenv(var)}")
            return True
    
    # Method 2: Check network configuration specific to Container Apps
    try:
        # Container Apps typically has this localhost address bound
        with open('/proc/net/tcp', 'r') as f:
            tcp_content = f.read()
            if '0100007F:0035' in tcp_content:  # 127.0.0.1:53 in hex
                logger.info("Azure detected via network configuration")
                return True
    except Exception:
        pass
    
    # Method 3: Check for Azure-specific filesystems or mounts
    try:
        with open('/proc/mounts', 'r') as f:
            mounts = f.read()
            if 'overlay' in mounts and 'containerd' in mounts:
                logger.info("Azure Container Apps detected via filesystem mounts")
                return True
    except Exception:
        pass
    
    logger.info("Not running in Azure based on all detection methods")
    return False

# Replace the old function call in get_backend_url
def get_backend_url():
    is_azure = is_running_in_azure()  # Use the new function instead
    
    # In Azure, use 'backend' without port
    if is_azure:
        backend_url = "http://backend"
        logger.info(f"Running in Azure environment, using URL: {backend_url}")
    else:
        # For local development, use port 5000
        backend_url = "http://backend:5000" 
        logger.info(f"Running in local environment, using URL: {backend_url}")
    
    return backend_url

@app.route('/test')
def test_connection():
    """
    Test route that attempts to connect to a backend URL provided as a query parameter.
    Example: /test?url=http://backend
    """
    logger.info("Received request to test backend connection")
    test_url = request.args.get('url', '')
    if not test_url:
        return jsonify({"error": "No URL provided. Use /test?url=http://backend"}), 400
    
    # Ensure test URL ends with /count
    if not test_url.endswith('/count'):
        test_url = f"{test_url.rstrip('/')}/count"
    
    result = {
        "test_url": test_url,
        "success": False,
        "response": None,
        "error": None,
        "status_code": None
    }
    
    try:
        logger.info(f"Testing connection to: {test_url}")
        response = requests.get(test_url, timeout=10)
        result["status_code"] = response.status_code
        
        if response.status_code == 200:
            result["success"] = True
            try:
                result["response"] = response.json()
            except:
                result["response"] = response.text
        else:
            result["error"] = f"HTTP Error: {response.status_code}"
            result["response"] = response.text
    except Exception as e:
        logger.error(f"Error connecting to {test_url}: {str(e)}")
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
    
    return jsonify(result)

# Get the backend URL based on environment
BACKEND_URL = get_backend_url()

@app.route('/')
def index():
    try:
        response = requests.get(f'{BACKEND_URL}/count')
        response.raise_for_status()
        count = response.json().get('count', 0)
    except requests.RequestException as e:
        logger.error(f"Error connecting to backend: {e}")
        count = 'Error fetching count'
    return render_template('index.html', count=count)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
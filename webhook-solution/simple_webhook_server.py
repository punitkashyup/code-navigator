#!/usr/bin/env python3
import os
import json
import logging
import hmac
import hashlib
import base64
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import traceback
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger()

# Import the lambda handler
try:
    from lambda_code_updater import process_code_changes
except ImportError as e:
    logger.error(f"Failed to import process_code_changes: {e}")
    exit(1)

# GitHub webhook secret for validation
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

def verify_signature(payload_body: str, signature_header: str) -> bool:
    """Verify that the payload was sent from GitHub by validating the signature."""
    if not WEBHOOK_SECRET or not signature_header:
        logger.warning("Webhook secret not configured or signature header missing")
        return False
    
    # GitHub uses sha256 prefixed with 'sha256='
    algorithm, signature = signature_header.split('=')
    if algorithm != 'sha256':
        logger.warning(f"Unexpected signature algorithm: {algorithm}")
        return False
    
    # Calculate expected signature
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body.encode(), digestmod=hashlib.sha256)
    expected_signature = mac.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

def transform_github_webhook_to_lambda_event(payload: dict) -> dict:
    """Transform GitHub webhook payload to our expected Lambda event format."""
    # Get repository info
    repo_url = payload.get('repository', {}).get('clone_url')
    repo_name = payload.get('repository', {}).get('full_name')
    ref = payload.get('ref', '')  # refs/heads/main
    
    # Extract branch name from ref
    branch = ref.replace('refs/heads/', '') if ref.startswith('refs/heads/') else 'main'
    
    # Get commit info
    commit_id = payload.get('after')
    
    # Get changed files from commits
    commits = payload.get('commits', [])
    added_files = []
    modified_files = []
    deleted_files = []
    
    for commit in commits:
        added_files.extend(commit.get('added', []))
        modified_files.extend(commit.get('modified', []))
        deleted_files.extend(commit.get('removed', []))
    
    # Remove duplicates
    added_files = list(set(added_files))
    modified_files = list(set(modified_files))
    deleted_files = list(set(deleted_files))
    
    # Create Lambda event format
    return {
        "repository": {
            "url": repo_url,
            "name": repo_name,
            "branch": branch
        },
        "added_files": added_files,
        "modified_files": modified_files,
        "deleted_files": deleted_files,
        "commit_id": commit_id
    }

def run_async_function(coro):
    """Run an async function in a new event loop in a separate thread (fire and forget)."""
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"Error in async processing: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            loop.close()
    
    # Start thread and don't wait for it to complete (fire and forget)
    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()
    # Don't call thread.join() - let it run in the background

class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.info(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "version": "1.0.0"}
            self.wfile.write(json.dumps(response).encode())
        elif parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "name": "Lambda-like Webhook Server",
                "endpoints": {
                    "/webhook": "POST - GitHub webhook endpoint",
                    "/health": "GET - Health check endpoint"
                }
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path != '/webhook':
            self.send_response(404)
            self.end_headers()
            return

        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            # Get headers
            signature = self.headers.get('X-Hub-Signature-256')
            github_event = self.headers.get('X-GitHub-Event')
            
            # Verify signature if configured
            if WEBHOOK_SECRET:
                if not signature:
                    logger.warning("Signature header missing")
                    self.send_response(401)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Signature header missing"}).encode())
                    return
                
                if not verify_signature(body, signature):
                    logger.warning("Invalid signature, rejecting webhook")
                    self.send_response(401)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid signature"}).encode())
                    return
            
            # Handle only push events
            if github_event != 'push':
                logger.info(f"Ignoring event type: {github_event}")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"message": f"Event {github_event} ignored"}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Parse GitHub payload
            try:
                github_payload = json.loads(body)
            except json.JSONDecodeError:
                logger.error("Invalid JSON payload")
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return
            
            # Transform to Lambda event format
            lambda_event = transform_github_webhook_to_lambda_event(github_payload)
            
            logger.info(f"Processing webhook for {lambda_event['repository']['name']}: "
                       f"{len(lambda_event['added_files'])} added, "
                       f"{len(lambda_event['modified_files'])} modified, "
                       f"{len(lambda_event['deleted_files'])} deleted")
            
            # Send immediate response to GitHub (before processing)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                "status": "accepted",
                "message": "Webhook received and processing started",
                "repository": lambda_event['repository']['name'],
                "branch": lambda_event['repository']['branch'],
                "files_count": {
                    "added": len(lambda_event['added_files']),
                    "modified": len(lambda_event['modified_files']),
                    "deleted": len(lambda_event['deleted_files'])
                }
            }
            self.wfile.write(json.dumps(response).encode())
            
            # Now start async processing (fire and forget)
            coro = process_code_changes(lambda_event, None)
            run_async_function(coro)
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            logger.error(traceback.format_exc())
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

def run_server():
    """Run the webhook server."""
    port = int(os.getenv("PORT", "8000"))
    server_address = ('', port)
    
    httpd = HTTPServer(server_address, WebhookHandler)
    logger.info(f"Starting Lambda-like webhook server on port {port}")
    logger.info(f"Webhook endpoint: http://localhost:{port}/webhook")
    logger.info(f"Health check: http://localhost:{port}/health")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        httpd.shutdown()

if __name__ == "__main__":
    run_server() 
import os
import json
import logging
import hmac
import hashlib
import base64
import asyncio
import boto3
from typing import Dict, Any

# Configure logging for Lambda
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import the main processing function
try:
    from lambda_code_updater import process_code_changes
except ImportError as e:
    logger.error(f"Failed to import process_code_changes: {e}")
    raise

# GitHub webhook secret for validation
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

def verify_signature(payload_body: str, signature_header: str) -> bool:
    """Verify that the payload was sent from GitHub by validating the signature."""
    if not WEBHOOK_SECRET or not signature_header:
        logger.warning("Webhook secret not configured or signature header missing")
        return False
    
    try:
        # GitHub uses sha256 prefixed with 'sha256='
        algorithm, signature = signature_header.split('=')
        if algorithm != 'sha256':
            logger.warning(f"Unexpected signature algorithm: {algorithm}")
            return False
        
        # Calculate expected signature
        mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body.encode(), digestmod=hashlib.sha256)
        expected_signature = mac.hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Error verifying signature: {str(e)}")
        return False

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

def create_response(status_code: int, body: dict, headers: dict = None) -> dict:
    """Create a proper API Gateway response."""
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body)
    }

def invoke_async_processing(lambda_event: dict, context):
    """Invoke the same Lambda function asynchronously for processing."""
    try:
        # Get current function name
        function_name = context.function_name
        logger.info(f"Invoking async processing for function: {function_name}")
        
        # Create payload for async processing
        async_payload = {
            "source": "async_processing", 
            "lambda_event": lambda_event
        }
        
        # Initialize Lambda client with timeout
        lambda_client = boto3.client(
            'lambda',
            config=boto3.session.Config(
                retries={'max_attempts': 1},
                read_timeout=5,  # 5 second timeout
                connect_timeout=2
            )
        )
        
        logger.info("Invoking Lambda function asynchronously...")
        
        # Invoke function asynchronously
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(async_payload)
        )
        
        status_code = response.get('StatusCode', 0)
        logger.info(f"Async invocation response - StatusCode: {status_code}")
        
        if status_code == 202:  # 202 is success for async invocations
            logger.info("Async processing invoked successfully")
            return True
        else:
            logger.warning(f"Unexpected status code from async invocation: {status_code}")
            return False
        
    except Exception as e:
        logger.error(f"Failed to invoke async processing: {str(e)}")
        import traceback
        logger.error(f"Async invocation traceback: {traceback.format_exc()}")
        return False

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    AWS Lambda handler for GitHub webhook processing via API Gateway.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    # Check if this is an async processing call
    if event.get("source") == "async_processing":
        logger.info("Processing async webhook processing call")
        try:
            lambda_event = event.get("lambda_event")
            if lambda_event:
                # Process the code changes asynchronously
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(process_code_changes(lambda_event, context))
                    logger.info(f"Async processing completed: {result}")
                    return {"statusCode": 200, "body": "Processing completed"}
                finally:
                    loop.close()
            else:
                logger.error("No lambda_event found in async processing call")
                return {"statusCode": 400, "body": "Invalid async processing payload"}
        except Exception as e:
            logger.error(f"Error in async processing: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"statusCode": 500, "body": str(e)}
    
    # Handle regular webhook processing
    try:
        # Handle CORS preflight requests
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, {"message": "CORS preflight"})
        
        # Handle GET requests (health check)
        if event.get('httpMethod') == 'GET':
            path = event.get('path', '/')
            
            if path == '/health':
                return create_response(200, {
                    "status": "healthy", 
                    "version": "1.0.0",
                    "lambda": True
                })
            elif path == '/':
                return create_response(200, {
                    "name": "AWS Lambda Webhook Handler",
                    "endpoints": {
                        "/webhook": "POST - GitHub webhook endpoint",
                        "/health": "GET - Health check endpoint"
                    }
                })
            else:
                return create_response(404, {"error": "Not found"})
        
        # Handle POST requests (webhook)
        if event.get('httpMethod') != 'POST':
            return create_response(405, {"error": "Method not allowed"})
        
        # Check if this is a webhook request
        path = event.get('path', '/')
        if path != '/webhook':
            return create_response(404, {"error": "Not found"})
        
        # Get request body
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body).decode('utf-8')
        
        # Get headers (API Gateway lowercases header names)
        headers = event.get('headers', {})
        signature = headers.get('x-hub-signature-256') or headers.get('X-Hub-Signature-256')
        github_event = headers.get('x-github-event') or headers.get('X-GitHub-Event')
        
        logger.info(f"Processing webhook event: {github_event}")
        
        # Verify signature if configured
        if WEBHOOK_SECRET:
            if not signature:
                logger.warning("Signature header missing")
                return create_response(401, {"error": "Signature header missing"})
            
            if not verify_signature(body, signature):
                logger.warning("Invalid signature, rejecting webhook")
                return create_response(401, {"error": "Invalid signature"})
        
        # Handle only push events
        if github_event != 'push':
            logger.info(f"Ignoring event type: {github_event}")
            return create_response(200, {"message": f"Event {github_event} ignored"})
        
        # Parse GitHub payload
        try:
            github_payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {str(e)}")
            return create_response(400, {"error": "Invalid JSON"})
        
        # Transform to our Lambda event format
        lambda_event = transform_github_webhook_to_lambda_event(github_payload)
        
        logger.info(f"Processing webhook for {lambda_event['repository']['name']}: "
                   f"{len(lambda_event['added_files'])} added, "
                   f"{len(lambda_event['modified_files'])} modified, "
                   f"{len(lambda_event['deleted_files'])} deleted")
        
        # Always prepare the response first
        response_body = {
            "status": "accepted",
            "message": "Webhook received successfully",
            "repository": lambda_event['repository']['name'],
            "branch": lambda_event['repository']['branch'],
            "files_count": {
                "added": len(lambda_event['added_files']),
                "modified": len(lambda_event['modified_files']),
                "deleted": len(lambda_event['deleted_files'])
            }
        }
        
        # Try to invoke async processing, but don't let it block the response
        async_processing_status = "unknown"
        try:
            logger.info("Attempting to start async processing...")
            
            # Set a hard timeout for async processing setup
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Async processing setup timed out")
            
            # Set 3-second timeout for async processing setup
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(3)
            
            try:
                async_success = invoke_async_processing(lambda_event, context)
                async_processing_status = "initiated" if async_success else "failed"
                logger.info(f"Async processing status: {async_processing_status}")
            finally:
                signal.alarm(0)  # Cancel the alarm
                
        except TimeoutError:
            logger.warning("Async processing setup timed out - proceeding with response")
            async_processing_status = "timeout"
        except Exception as e:
            logger.error(f"Exception during async processing setup: {str(e)}")
            async_processing_status = "error"
        
        # Update response based on async processing result
        response_body["async_processing"] = async_processing_status
        if async_processing_status == "initiated":
            response_body["message"] = "Webhook received and processing started"
        elif async_processing_status == "failed":
            response_body["message"] = "Webhook received but processing failed to start"
        elif async_processing_status == "timeout":
            response_body["message"] = "Webhook received, processing may have started"
        else:
            response_body["message"] = "Webhook received but processing status unknown"
        
        # Always return response to GitHub
        logger.info(f"Sending response to GitHub: {response_body}")
        return create_response(200, response_body)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return create_response(500, {"error": str(e)})

# For local testing
if __name__ == "__main__":
    # Test event for local development
    test_event = {
        "httpMethod": "GET",
        "path": "/health",
        "headers": {},
        "body": "",
        "isBase64Encoded": False
    }
    
    class MockContext:
        def __init__(self):
            self.function_name = "test"
            self.function_version = "1"
            self.invoked_function_arn = "test"
            self.memory_limit_in_mb = 128
            self.remaining_time_in_millis = lambda: 30000
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2)) 
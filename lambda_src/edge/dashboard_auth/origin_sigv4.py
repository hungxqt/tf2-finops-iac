import json
import os
import botocore.session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

try:
    import config
    TARGET_REGION = config.TARGET_REGION
    TARGET_SERVICE = config.TARGET_SERVICE
except ImportError:
    TARGET_REGION = "ap-southeast-1"
    TARGET_SERVICE = "lambda"

def handler(event, context):
    request = event['Records'][0]['cf']['request']
    headers = request['headers']
    
    # Construct headers dict for SigV4 signing
    signing_headers = {}
    for name, value_list in headers.items():
        # Skip headers that should not be signed or will be overwritten
        if name in ('x-forwarded-for', 'via', 'connection', 'authorization', 'x-amz-date', 'x-amz-security-token'):
            continue
        if value_list:
            signing_headers[value_list[0]['key']] = value_list[0]['value']
            
    # Set Host header to the domain name of the custom origin (ALB)
    domain_name = request['origin']['custom']['domainName']
    signing_headers['Host'] = domain_name
    
    # Strip Cognito access and ID token cookies to avoid exposing them to the ALB/AI engine
    if 'cookie' in headers:
        # Filter cookies to remove Cognito ones
        cookie_header_val = headers['cookie'][0]['value']
        non_cognito_cookies = []
        for cookie in cookie_header_val.split(';'):
            if '=' in cookie:
                k, v = cookie.split('=', 1)
                k = k.strip()
                if not k.startswith('Cognito-'):
                    non_cognito_cookies.append(cookie.strip())
        
        if non_cognito_cookies:
            cookie_val = '; '.join(non_cognito_cookies)
            headers['cookie'] = [{'key': 'Cookie', 'value': cookie_val}]
            signing_headers['Cookie'] = cookie_val
        else:
            del headers['cookie']
            if 'Cookie' in signing_headers:
                del signing_headers['Cookie']
            
    # Extract body if present
    body = b''
    if 'body' in request and request['body'].get('data'):
        body_data = request['body']['data']
        if request['body'].get('encoding') == 'base64':
            import base64
            body = base64.b64decode(body_data)
        else:
            body = body_data.encode('utf-8')
            
    # Construct full URL for signing
    url = f"https://{domain_name}{request['uri']}"
    if request.get('querystring'):
        url += f"?{request['querystring']}"
        
    session = botocore.session.Session()
    credentials = session.get_credentials()
    if not credentials:
        return request
        
    frozen_credentials = credentials.get_frozen_credentials()
    
    aws_req = AWSRequest(
        method=request['method'],
        url=url,
        headers=signing_headers,
        data=body
    )
    
    auth = SigV4Auth(frozen_credentials, TARGET_SERVICE, TARGET_REGION)
    auth.add_auth(aws_req)
    
    # Map signed headers back to CloudFront request headers
    for name, value in aws_req.headers.items():
        headers[name.lower()] = [{'key': name, 'value': str(value)}]
        
    # Overwrite the host header to match the origin ALB domain name
    headers['host'] = [{'key': 'Host', 'value': domain_name}]
    
    return request

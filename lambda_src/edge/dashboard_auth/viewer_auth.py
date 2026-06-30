import json
import urllib.parse
import urllib.request
import urllib.error
import secrets
import hashlib
import base64
import time
import boto3

try:
    import config
    COGNITO_DOMAIN = config.COGNITO_DOMAIN
    USER_POOL_ID = config.USER_POOL_ID
    REGION = config.REGION
    COGNITO_CLIENT_ID_PARAM = config.COGNITO_CLIENT_ID_PARAM
except ImportError:
    COGNITO_DOMAIN = ""
    USER_POOL_ID = ""
    REGION = "ap-southeast-1"
    COGNITO_CLIENT_ID_PARAM = ""

CLIENT_ID = None
AUTH_COOKIE_MAX_AGE_SECONDS = 3600
PKCE_COOKIE_MAX_AGE_SECONDS = 300
CSRF_COOKIE_MAX_AGE_SECONDS = 300

def get_client_id():
    global CLIENT_ID
    if CLIENT_ID is None:
        if not COGNITO_CLIENT_ID_PARAM:
            return None
        try:
            ssm = boto3.client('ssm', region_name=REGION)
            param = ssm.get_parameter(Name=COGNITO_CLIENT_ID_PARAM, WithDecryption=True)
            CLIENT_ID = param['Parameter']['Value']
        except Exception:
            pass
    return CLIENT_ID

def parse_cookies(headers):
    cookies = {}
    if 'cookie' in headers:
        for cookie_header in headers['cookie']:
            cookie_val = cookie_header['value']
            for cookie in cookie_val.split(';'):
                if '=' in cookie:
                    k, v = cookie.split('=', 1)
                    cookies[k.strip()] = v.strip()
    return cookies

def base64url_decode(payload):
    rem = len(payload) % 4
    if rem > 0:
        payload += '=' * (4 - rem)
    return base64.urlsafe_b64decode(payload.encode('utf-8'))

def parse_jwt(token):
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload_json = base64url_decode(parts[1])
        return json.loads(payload_json)
    except Exception:
        return None

def base64url_encode(payload):
    return base64.urlsafe_b64encode(payload).decode('utf-8').rstrip('=')

def encode_state(redirect_path, nonce):
    payload = {
        'redirect': redirect_path if redirect_path.startswith('/') and not redirect_path.startswith('//') else '/',
        'nonce': nonce
    }
    return base64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))

def decode_state(state):
    try:
        payload = json.loads(base64url_decode(state))
        redirect = payload.get('redirect', '/')
        if not redirect.startswith('/') or redirect.startswith('//'):
            redirect = '/'
        return {
            'redirect': redirect,
            'nonce': payload.get('nonce')
        }
    except Exception:
        return {'redirect': '/', 'nonce': None}

def validate_claims(payload, client_id, user_pool_id, region):
    if not payload or not client_id:
        return False
    now = time.time()
    if payload.get('exp', 0) < now:
        return False
    expected_iss = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    if payload.get('iss') != expected_iss:
        return False
    if payload.get('client_id') != client_id and payload.get('aud') != client_id:
        return False
    return True

def verify_token_with_cognito(access_token, cognito_domain):
    url = f"https://{cognito_domain}/oauth2/userInfo"
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Bearer {access_token}')
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True
    except Exception:
        pass
    return False

def make_redirect(location, cookies_to_set=None, cookies_to_clear=None):
    headers = {
        'location': [{'key': 'Location', 'value': location}]
    }
    cookie_headers = []
    if cookies_to_set:
        for k, cookie in cookies_to_set.items():
            if isinstance(cookie, dict):
                value = cookie['value']
                max_age = cookie.get('max_age', AUTH_COOKIE_MAX_AGE_SECONDS)
                same_site = cookie.get('same_site', 'Strict')
            else:
                value = cookie
                max_age = AUTH_COOKIE_MAX_AGE_SECONDS
                same_site = 'Strict'
            cookie_headers.append({
                'key': 'Set-Cookie',
                'value': f"{k}={value}; Path=/; Secure; HttpOnly; SameSite={same_site}; Max-Age={max_age}"
            })
    if cookies_to_clear:
        for k in cookies_to_clear:
            cookie_headers.append({
                'key': 'Set-Cookie',
                'value': f"{k}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT"
            })
    if cookie_headers:
        headers['set-cookie'] = cookie_headers
    return {
        'status': '302',
        'statusDescription': 'Found',
        'headers': headers
    }

def handler(event, context):
    client_id = get_client_id()
    if not client_id:
        return {
            'status': '500',
            'statusDescription': 'Internal Server Error',
            'body': 'Failed to retrieve Cognito Client ID from SSM'
        }

    request = event['Records'][0]['cf']['request']
    headers = request['headers']
    uri = request['uri']
    
    host = headers.get('host', [{}])[0].get('value', '')
    if not host:
        return request
        
    redirect_uri = f"https://{host}/oauth2/callback"
    
    # 1. Handle Logout
    if uri == '/logout':
        cognito_logout_url = f"https://{COGNITO_DOMAIN}/logout?client_id={client_id}&logout_uri=https://{host}"
        return make_redirect(
            cognito_logout_url,
            cookies_to_clear=['Cognito-Access-Token', 'Cognito-Id-Token', 'Cognito-PKCE-Verifier', 'Cognito-CSRF-Nonce']
        )
        
    # 2. Handle Cognito Callback
    if uri == '/oauth2/callback':
        params = urllib.parse.parse_qs(request.get('querystring', ''))
        code = params.get('code', [None])[0]
        state = params.get('state', [None])[0]
        
        cookies = parse_cookies(headers)
        verifier = cookies.get('Cognito-PKCE-Verifier')
        csrf_nonce = cookies.get('Cognito-CSRF-Nonce')
        decoded_state = decode_state(state) if state else {'redirect': '/', 'nonce': None}
        
        if not code or not verifier or not csrf_nonce or decoded_state.get('nonce') != csrf_nonce:
            return make_redirect('/')
            
        token_url = f"https://{COGNITO_DOMAIN}/oauth2/token"
        data = urllib.parse.urlencode({
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': verifier
        }).encode('utf-8')
        
        req = urllib.request.Request(token_url, data=data)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                tokens = json.loads(response.read().decode('utf-8'))
                access_token = tokens.get('access_token')
                id_token = tokens.get('id_token')
                
                if access_token and id_token:
                    cookies_to_set = {
                        'Cognito-Access-Token': {
                            'value': access_token,
                            'max_age': AUTH_COOKIE_MAX_AGE_SECONDS,
                            'same_site': 'Lax'
                        },
                        'Cognito-Id-Token': {
                            'value': id_token,
                            'max_age': AUTH_COOKIE_MAX_AGE_SECONDS,
                            'same_site': 'Lax'
                        }
                    }
                    return make_redirect(
                        decoded_state['redirect'],
                        cookies_to_set=cookies_to_set,
                        cookies_to_clear=['Cognito-PKCE-Verifier', 'Cognito-CSRF-Nonce']
                    )
        except Exception as e:
            return {
                'status': '500',
                'statusDescription': 'Internal Server Error',
                'body': f"Failed to exchange code: {str(e)}"
            }
            
    # 3. Check for existing cookies
    cookies = parse_cookies(headers)
    access_token = cookies.get('Cognito-Access-Token')
    
    if access_token:
        payload = parse_jwt(access_token)
        if validate_claims(payload, client_id, USER_POOL_ID, REGION):
            if verify_token_with_cognito(access_token, COGNITO_DOMAIN):
                return request
                
    # 4. Initiate PKCE Flow
    verifier = secrets.token_urlsafe(64)
    csrf_nonce = secrets.token_urlsafe(32)
    sha256_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
    challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip('=')
    
    redirect_path = request.get('uri', '/')
    if request.get('querystring'):
        redirect_path += f"?{request['querystring']}"
    state = encode_state(redirect_path, csrf_nonce)
        
    cognito_auth_url = (
        f"https://{COGNITO_DOMAIN}/login?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"scope={urllib.parse.quote('openid email profile')}&"
        f"state={urllib.parse.quote(state)}&"
        f"code_challenge={challenge}&"
        f"code_challenge_method=S256"
    )
    
    return make_redirect(
        cognito_auth_url,
        cookies_to_set={
            'Cognito-PKCE-Verifier': {'value': verifier, 'max_age': PKCE_COOKIE_MAX_AGE_SECONDS, 'same_site': 'Lax'},
            'Cognito-CSRF-Nonce': {'value': csrf_nonce, 'max_age': CSRF_COOKIE_MAX_AGE_SECONDS, 'same_site': 'Lax'}
        }
    )

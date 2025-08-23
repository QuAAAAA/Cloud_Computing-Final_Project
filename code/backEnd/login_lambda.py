import json
import boto3
import hashlib
from datetime import datetime
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
BUCKET_NAME = 'awslambda0521'
USERS_PROFILES_PREFIX = 'users/profiles/'

def lambda_handler(event, context):
    http_method = event.get('httpMethod', '')

    print(f"DEBUG: event = {json.dumps(event)}")

    try:
        if 'body' not in event or not event['body']:
            return response(400, '請求體不能為空')

        try:
            request_body = json.loads(event['body'])
        except json.JSONDecodeError:
            return response(400, '無效的 JSON 格式')

        username = request_body.get('username')
        password = request_body.get('password')

        if not username or not password:
            return response(400, '用戶名和密碼為必填項目')

        # 驗證用戶
        user_data = load_user_profile(username)
        if not user_data:
            print("error login")
            return response(401, '用戶名或密碼錯誤')

        # 檢查帳號是否啟用
        if not user_data.get('isActive', True):
            return response(403, '帳號已被停用，請聯繫管理員')

        # 驗證密碼
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        if user_data.get('password') != hashed_password:
            print("error login")
            return response(401, '用戶名或密碼錯誤')

        # 更新登入資訊
        current_time = datetime.utcnow().isoformat() + 'Z'
        user_data['lastLogin'] = current_time
        user_data['loginCount'] = user_data.get('loginCount', 0) + 1

        # 儲存更新的用戶資料
        save_user_profile(username, user_data)

        print(f"User {username} logged in successfully.")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': '登入成功',
                'username': username,
                'email': user_data.get('email'),
                'lastLogin': user_data.get('lastLogin'),
                'loginCount': user_data.get('loginCount'),
                'role': 'admin' if username == 'admin' else 'user'
            }, ensure_ascii=False)
        }

    except ClientError as e:
        print(f"AWS ClientError: {str(e)}")
        return response(500, 'AWS操作失敗，請稍後再試')

    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return response(500, '伺服器內部錯誤')

def load_user_profile(username):
    """載入用戶個人資料"""
    try:
        profile_key = f'{USERS_PROFILES_PREFIX}{username}.json'
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=profile_key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"User profile not found: {username}")
            return None
        else:
            print(f"Error loading user profile: {str(e)}")
            raise e
    except Exception as e:
        print(f"讀取用戶資料時發生錯誤: {str(e)}")
        return None

def save_user_profile(username, user_data):
    """儲存用戶個人資料"""
    try:
        profile_key = f'{USERS_PROFILES_PREFIX}{username}.json'
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=profile_key,
            Body=json.dumps(user_data, ensure_ascii=False),
            ContentType='application/json'
        )
        print(f"User profile saved: {username}")
    except Exception as e:
        print(f"儲存用戶資料時發生錯誤: {str(e)}")
        raise e

def response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'message': message}, ensure_ascii=False)
    }
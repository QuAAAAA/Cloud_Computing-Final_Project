import json
import boto3
import hashlib
from datetime import datetime
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
BUCKET_NAME = 'awslambda0521'
USERS_INDEX_KEY = 'users/users.json'
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
        email = request_body.get('email')
        password = request_body.get('password')

        if not username or not email or not password:
            return response(400, '用戶名、電子郵件和密碼為必填項目')

        if not username.replace('_', '').isalnum() or len(username) < 3:
            return response(400, '用戶名必須至少3個字符，只能包含字母、數字和下劃線')

        if len(password) < 6:
            return response(400, '密碼至少需要6個字符')

        users_data = load_users_index()
        if username in [u['username'] for u in users_data['users']]:
            return response(409, '用戶名已存在')

        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        current_time = datetime.utcnow().isoformat() + 'Z'

        user_index_data = {
            'username': username,
            'email': email,
            'createdAt': current_time,
            'lastLogin': None,
            'profilePath': f'{USERS_PROFILES_PREFIX}{username}.json'
        }

        user_profile_data = {
            'username': username,
            'email': email,
            'password': hashed_password,
            'createdAt': current_time,
            'lastLogin': None,
            'loginCount': 0,
            'isActive': True
        }

        # 寫入個人資料檔案
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=f'{USERS_PROFILES_PREFIX}{username}.json',
            Body=json.dumps(user_profile_data, ensure_ascii=False),
            ContentType='application/json'
        )

        # 更新總索引
        users_data['users'].append(user_index_data)
        users_data['lastUpdated'] = current_time

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=USERS_INDEX_KEY,
            Body=json.dumps(users_data, ensure_ascii=False),
            ContentType='application/json'
        )

        print(f"User {username} created successfully.")
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'message': '用戶創建成功',
                'username': username
            }, ensure_ascii=False)
        }

    except ClientError as e:
        print(f"AWS ClientError: {str(e)}")
        return response(500, 'AWS操作失敗，請稍後再試')

    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return response(500, '伺服器內部錯誤')

def load_users_index():
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=USERS_INDEX_KEY)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("users.json 不存在，將創建新索引")
            return {
                'users': [],
                'lastUpdated': datetime.utcnow().isoformat() + 'Z'
            }
        else:
            raise e
    except Exception as e:
        print(f"讀取 users index 時發生錯誤: {str(e)}")
        return {
            'users': [],
            'lastUpdated': datetime.utcnow().isoformat() + 'Z'
        }

def response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'message': message}, ensure_ascii=False)
    }
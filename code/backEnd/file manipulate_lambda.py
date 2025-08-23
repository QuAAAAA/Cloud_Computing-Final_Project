import json
import base64
import boto3
import re
import os
from datetime import datetime
from botocore.exceptions import ClientError

# S3 存储桶配置
output_bucket = 'awslambda0521'
s3_client = boto3.client('s3')

# 文件存储路径配置
FILES_PREFIX = 'files/'
USER_FILES_INDEX = 'files/user_files_index.json'

# CORS 配置
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, GET, DELETE, OPTIONS'
}

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    # 處理 OPTIONS 請求 (CORS preflight)
    http_method = (
        event.get('httpMethod') or  # v1.0
        event.get('requestContext', {}).get('http', {}).get('method', '')  # v2.0
    )   
    print("HTTP Method:", http_method)

    if http_method.upper() == 'OPTIONS':
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps("CORS OK")
        }
    
    try:
        # 檢查請求類型
        content_type = ""
        if 'headers' in event:
            headers = event['headers']
            content_type = headers.get('content-type', headers.get('Content-Type', ''))
        
        # 處理 GET 請求 - 獲取用戶文件列表
        if http_method.upper() == 'GET':
            return handle_get_files(event)
        
        # 處理 DELETE 請求 - 刪除文件
        elif http_method.upper() == 'DELETE':
            return handle_delete_file(event)
        
        # 處理 PUT 請求 - 重新命名文件
        elif http_method.upper() == 'PUT':
            return handle_rename_file(event)
        
        # 處理 POST 請求 - 上傳文件
        elif http_method.upper() == 'POST':
            if 'multipart/form-data' in content_type:
                return handle_multipart_upload(event, content_type)
            elif 'application/json' in content_type:
                return handle_json_upload(event)
            else:
                return response(400, 'Unsupported content type')
        
        else:
            print(f"Unsupported method received: {http_method}")
            return response(400, f'Unsupported HTTP method: {http_method}')
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, f'Internal server error: {str(e)}')

def handle_get_files(event):
    """處理獲取用戶文件列表的請求"""
    try:
        # 從查詢參數獲取用戶名
        query_params = event.get('queryStringParameters', {}) or {}
        username = query_params.get('username')
        
        if not username:
            return response(400, 'Missing username parameter')
        
        # 獲取用戶的文件列表
        user_files = get_user_files(username)
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'files': user_files,
                'count': len(user_files)
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f"Error getting files: {str(e)}")
        return response(500, 'Failed to get files')

def handle_delete_file(event):
    """處理刪除文件的請求"""
    try:
        # 從查詢參數獲取文件信息
        query_params = event.get('queryStringParameters', {}) or {}
        username = query_params.get('username')
        filename = query_params.get('filename')
        
        if not username or not filename:
            return response(400, 'Missing username or filename parameter')
        
        # 刪除文件
        success = delete_user_file(username, filename)
        
        if success:
            return {
                'statusCode': 200,
                'headers': CORS_HEADERS,
                'body': json.dumps({'message': '文件刪除成功'}, ensure_ascii=False)
            }
        else:
            return response(404, 'File not found')
            
    except Exception as e:
        print(f"Error deleting file: {str(e)}")
        return response(500, 'Failed to delete file')

def handle_multipart_upload(event, content_type):
    """處理 multipart/form-data 格式的上傳"""
    try:
        if 'body' in event and event.get('isBase64Encoded', False):
            # 獲取原始二進制數據
            body_binary = base64.b64decode(event['body'])
            
            # 解析 multipart 數據
            boundary_match = re.search(r'boundary=([^;]+)', content_type)
            if not boundary_match:
                return response(400, 'Could not find multipart boundary')
            
            boundary = boundary_match.group(1)
            boundary_bytes = f'--{boundary}'.encode('utf-8')
            
            # 分解 multipart 數據
            parts = body_binary.split(boundary_bytes)
            
            file_content = None
            filename = None
            username = None
            
            # 解析每個部分
            for part in parts:
                if len(part) < 10:
                    continue
                
                part_str = part.decode('utf-8', errors='replace')
                
                # 檢查是否是文件部分
                if 'Content-Disposition' in part_str and 'filename=' in part_str:
                    filename_match = re.search(r'filename="([^"]+)"', part_str)
                    if filename_match:
                        filename = filename_match.group(1)
                    
                    headers_end = part.find(b'\r\n\r\n')
                    if headers_end > 0:
                        file_content = part[headers_end + 4:]
                        if file_content.endswith(b'--\r\n'):
                            file_content = file_content[:-4]
                        if file_content.endswith(b'\r\n'):
                            file_content = file_content[:-2]
                
                # 檢查是否是用戶名部分
                elif 'Content-Disposition' in part_str and 'name="username"' in part_str:
                    headers_end = part.find(b'\r\n\r\n')
                    if headers_end > 0:
                        username_content = part[headers_end + 4:]
                        if username_content.endswith(b'\r\n'):
                            username_content = username_content[:-2]
                        username = username_content.decode('utf-8').strip()
            
            if file_content is not None and filename and username:
                # 上傳文件
                return upload_file_to_s3(username, filename, file_content)
            else:
                return response(400, 'Missing file content, filename, or username')
        else:
            return response(400, 'Expected base64 encoded body')
            
    except Exception as e:
        print(f"Error in multipart upload: {str(e)}")
        return response(500, f'Upload failed: {str(e)}')

def handle_json_upload(event):
    """處理 JSON 格式的上傳"""
    try:
        if 'body' in event:
            body = event['body']
            if isinstance(body, str):
                try:
                    request_body = json.loads(body)
                except:
                    return response(400, 'Invalid JSON body')
            else:
                request_body = body
            
            if 'key' in request_body and 'username' in request_body:
                username = request_body['username']
                filename = request_body.get('filename', f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                
                # 處理 base64 編碼的圖片
                image_data = base64.decodebytes(request_body['key'].encode('utf-8'))
                
                return upload_file_to_s3(username, filename, image_data)
            else:
                return response(400, 'Missing "key" or "username" field in request body')
                
    except Exception as e:
        print(f"Error in JSON upload: {str(e)}")
        return response(500, f'Upload failed: {str(e)}')

def upload_file_to_s3(username, original_filename, file_content):
    """上傳文件到 S3 並更新用戶文件索引"""
    try:
        # 確保用戶目錄存在
        ensure_user_directory(username)
        
        # 清理文件名以確保安全
        safe_filename = re.sub(r'[^\w\.-]', '_', original_filename)
        
        # 生成唯一的文件名（加入時間戳避免重複）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(safe_filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        
        # 構建 S3 鍵值（路徑）
        s3_key = f"{FILES_PREFIX}{username}/{unique_filename}"
        
        # 根據文件擴展名確定 Content-Type
        content_type = get_content_type(safe_filename)
        
        # 上傳到 S3
        s3_client.put_object(
            Bucket=output_bucket,
            Key=s3_key,
            Body=file_content,
            ACL='public-read',
            ContentType=content_type
        )
        
        # 獲取文件大小
        file_size = len(file_content)
        file_size_str = format_file_size(file_size)
        
        # 構建文件 URL
        s3_url = f'https://{output_bucket}.s3.amazonaws.com/{s3_key}'
        
        # 更新用戶文件索引
        file_info = {
            'name': original_filename,
            'uniqueName': unique_filename,
            's3Key': s3_key,
            'url': s3_url,
            'size': file_size_str,
            'uploadDate': datetime.now().strftime('%Y-%m-%d'),
            'uploadTime': datetime.now().isoformat() + 'Z',
            'type': content_type
        }
        
        add_file_to_index(username, file_info)
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'message': '文件上傳成功',
                'url': s3_url,
                'filename': unique_filename,
                'size': file_size_str
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")
        return response(500, f'Upload to S3 failed: {str(e)}')

def get_user_files(username):
    """獲取用戶的文件列表"""
    try:
        # 確保索引文件存在
        ensure_files_index()
        
        # 從 S3 獲取用戶文件索引
        try:
            response = s3_client.get_object(Bucket=output_bucket, Key=USER_FILES_INDEX)
            content = response['Body'].read().decode('utf-8')
            files_index = json.loads(content)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                ensure_files_index()
                return []
            else:
                raise e
        
        # 返回指定用戶的文件
        return files_index.get(username, [])
        
    except Exception as e:
        print(f"Error getting user files: {str(e)}")
        return []

def add_file_to_index(username, file_info):
    """將文件信息添加到用戶文件索引"""
    try:
        # 確保索引文件存在
        ensure_files_index()
        
        # 讀取現有索引
        try:
            response = s3_client.get_object(Bucket=output_bucket, Key=USER_FILES_INDEX)
            content = response['Body'].read().decode('utf-8')
            files_index = json.loads(content)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                files_index = {}
            else:
                raise e
        
        # 初始化用戶文件列表
        if username not in files_index:
            files_index[username] = []
        
        # 添加新文件信息
        files_index[username].append(file_info)
        
        # 保存更新的索引
        s3_client.put_object(
            Bucket=output_bucket,
            Key=USER_FILES_INDEX,
            Body=json.dumps(files_index, ensure_ascii=False),
            ContentType='application/json'
        )
        
        print(f"Added file to index for user {username}: {file_info['name']}")
        
    except Exception as e:
        print(f"Error updating file index: {str(e)}")
        raise e

def delete_user_file(username, filename):
    """刪除用戶的文件"""
    try:
        # 讀取文件索引
        try:
            response = s3_client.get_object(Bucket=output_bucket, Key=USER_FILES_INDEX)
            content = response['Body'].read().decode('utf-8')
            files_index = json.loads(content)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return False
            else:
                raise e
        
        # 查找要刪除的文件
        user_files = files_index.get(username, [])
        file_to_delete = None
        file_index = -1
        
        for i, file_info in enumerate(user_files):
            if file_info['name'] == filename or file_info['uniqueName'] == filename:
                file_to_delete = file_info
                file_index = i
                break
        
        if file_to_delete is None:
            return False
        
        # 從 S3 刪除文件
        try:
            s3_client.delete_object(Bucket=output_bucket, Key=file_to_delete['s3Key'])
        except Exception as e:
            print(f"Error deleting file from S3: {str(e)}")
        
        # 從索引中移除文件
        user_files.pop(file_index)
        
        # 保存更新的索引
        s3_client.put_object(
            Bucket=output_bucket,
            Key=USER_FILES_INDEX,
            Body=json.dumps(files_index, ensure_ascii=False),
            ContentType='application/json'
        )
        
        print(f"Deleted file for user {username}: {filename}")
        return True
        
    except Exception as e:
        print(f"Error deleting file: {str(e)}")
        return False

def get_content_type(filename):
    """根據文件擴展名獲取 Content-Type"""
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml'
    }
    return content_types.get(ext, 'application/octet-stream')

def ensure_user_directory(username):
    """確保用戶目錄存在（在 S3 中創建目錄標記）"""
    try:
        # 在 S3 中，我們通過創建一個空的 "目錄標記" 對象來表示目錄
        directory_key = f"{FILES_PREFIX}{username}/"
        
        # 檢查目錄是否已存在
        try:
            s3_client.head_object(Bucket=output_bucket, Key=directory_key)
            print(f"User directory already exists: {directory_key}")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # 目錄不存在，創建它
                s3_client.put_object(
                    Bucket=output_bucket,
                    Key=directory_key,
                    Body='placeholder for directory'
                )
                print(f"Created user directory: {directory_key}")
            else:
                raise e
                
    except Exception as e:
        print(f"Error ensuring user directory: {str(e)}")
        # 即使目錄創建失敗，我們仍然可以繼續上傳文件
        # S3 會自動創建路徑結構

def ensure_files_index():
    """確保文件索引存在"""
    try:
        # 檢查索引文件是否存在
        try:
            s3_client.head_object(Bucket=output_bucket, Key=USER_FILES_INDEX)
            print("Files index already exists")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # 索引文件不存在，創建空索引
                empty_index = {}
                s3_client.put_object(
                    Bucket=output_bucket,
                    Key=USER_FILES_INDEX,
                    Body=json.dumps(empty_index, ensure_ascii=False),
                    ContentType='application/json'
                )
                print("Created empty files index")
            else:
                raise e
                
    except Exception as e:
        print(f"Error ensuring files index: {str(e)}")
        # 如果無法創建索引文件，add_file_to_index 函數會處理這個問題

# 格式化文件大小函式
def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def response(status_code, message):
    """標準化響應格式"""
    return {
        'statusCode': status_code,
        'headers': {
            **CORS_HEADERS,
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'message': message}, ensure_ascii=False)
    }

# 新增：處理重新命名文件的請求
import json
import re
import os
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def handle_rename_file(event):
    """處理重新命名文件的請求"""
    try:
        # 驗證請求體
        if 'body' not in event:
            return response(400, '缺少請求主體')
        
        body = event['body']
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError as e:
                return response(400, f'無效的JSON格式: {str(e)}')
        
        # 提取參數
        username = body.get('username', '').strip()
        old_name = body.get('oldName', '').strip()
        new_name = body.get('newName', '').strip()
        
        # 參數驗證
        if not username:
            return response(400, '缺少使用者名稱')
        if not old_name:
            return response(400, '缺少原始檔案名稱')
        if not new_name:
            return response(400, '缺少新檔案名稱')
        
        # 檔名驗證
        validation_result = validate_filename(new_name)
        if not validation_result['valid']:
            return response(400, validation_result['message'])
        
        # 檢查新舊檔名是否相同
        if old_name == new_name:
            return response(400, '新檔名與原檔名相同')
        
        # 讀取使用者檔案索引
        try:
            response_s3 = s3_client.get_object(Bucket=output_bucket, Key=USER_FILES_INDEX)
            files_index = json.loads(response_s3['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return response(404, '檔案索引不存在')
            else:
                return response(500, f'讀取檔案索引失敗: {str(e)}')
        except Exception as e:
            return response(500, f'處理檔案索引時發生錯誤: {str(e)}')
        
        user_files = files_index.get(username, [])
        if not user_files:
            return response(404, '使用者沒有檔案')
        
        # 尋找目標檔案
        target_file = None
        target_index = -1
        for i, f in enumerate(user_files):
            if f.get('name') == old_name or f.get('uniqueName') == old_name:
                target_file = f
                target_index = i
                break
        
        if not target_file:
            return response(404, f'找不到檔案: {old_name}')
        
        # 檢查新檔名是否已存在
        for f in user_files:
            if f.get('name') == new_name and f != target_file:
                return response(409, f'檔名「{new_name}」已存在，請選擇其他名稱')
        
        # 產生新的唯一檔名
        original_name, ext = os.path.splitext(target_file.get('name', ''))
        new_ext = os.path.splitext(new_name)[1] or ext  # 保持原副檔名如果新名稱沒有副檔名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 清理檔名，移除特殊字符
        sanitized_new_name = sanitize_filename(new_name)
        new_unique_name = f"{sanitized_new_name}_{timestamp}{new_ext}"
        new_s3_key = f"{FILES_PREFIX}{username}/{new_unique_name}"
        
        # 執行S3操作
        try:
            # 複製檔案到新位置
            copy_source = {
                'Bucket': output_bucket, 
                'Key': target_file.get('s3Key', '')
            }
            
            s3_client.copy_object(
                Bucket=output_bucket,
                CopySource=copy_source,
                Key=new_s3_key,
                ACL='public-read',
                ContentType=target_file.get('type', 'application/octet-stream'),
                MetadataDirective='COPY'
            )
            
            # 驗證新檔案是否成功創建
            try:
                s3_client.head_object(Bucket=output_bucket, Key=new_s3_key)
            except ClientError:
                return response(500, '新檔案創建失敗')
            
            # 刪除原始檔案
            s3_client.delete_object(
                Bucket=output_bucket, 
                Key=target_file.get('s3Key', '')
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                return response(404, '原始檔案在儲存中不存在')
            elif error_code == 'AccessDenied':
                return response(403, '沒有權限執行此操作')
            else:
                return response(500, f'S3操作失敗: {str(e)}')
        except Exception as e:
            return response(500, f'檔案操作時發生未預期錯誤: {str(e)}')
        
        # 更新檔案索引
        current_time = datetime.now()
        files_index[username][target_index].update({
            'name': new_name,
            'uniqueName': new_unique_name,
            's3Key': new_s3_key,
            'url': f'https://{output_bucket}.s3.amazonaws.com/{new_s3_key}',
            'lastModified': current_time.strftime('%Y-%m-%d'),
            'lastModifiedTime': current_time.isoformat() + 'Z'
        })
        
        # 儲存更新後的索引
        try:
            s3_client.put_object(
                Bucket=output_bucket,
                Key=USER_FILES_INDEX,
                Body=json.dumps(files_index, ensure_ascii=False, indent=2),
                ContentType='application/json'
            )
        except Exception as e:
            # 如果索引更新失敗，嘗試回滾
            try:
                s3_client.delete_object(Bucket=output_bucket, Key=new_s3_key)
                s3_client.copy_object(
                    Bucket=output_bucket,
                    CopySource=copy_source,
                    Key=target_file.get('s3Key', ''),
                    ACL='public-read',
                    ContentType=target_file.get('type', 'application/octet-stream')
                )
            except:
                pass  # 回滾失敗，記錄錯誤但不影響回應
            
            return response(500, f'更新檔案索引失敗: {str(e)}')
        
        return response(200, '檔案重新命名成功', {
            'oldName': old_name,
            'newName': new_name,
            'newUrl': f'https://{output_bucket}.s3.amazonaws.com/{new_s3_key}'
        })
        
    except NoCredentialsError:
        return response(500, 'AWS認證失敗')
    except Exception as e:
        print(f"重新命名檔案時發生未預期錯誤: {str(e)}")
        return response(500, f'內部伺服器錯誤: {str(e)}')

def validate_filename(filename):
    """驗證檔名是否符合規範"""
    if not filename or len(filename.strip()) == 0:
        return {'valid': False, 'message': '檔名不能為空'}
    
    if len(filename) > 255:
        return {'valid': False, 'message': '檔名過長，請限制在255個字符以內'}
    
    # 檢查非法字符
    invalid_chars = r'[<>:"|?*\\/]'
    if re.search(invalid_chars, filename):
        return {'valid': False, 'message': '檔名不能包含以下字符：< > : " | ? * \\ /'}
    
    # 檢查Windows保留名稱
    reserved_names = r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)'
    if re.match(reserved_names, filename, re.IGNORECASE):
        return {'valid': False, 'message': '檔名不能使用系統保留名稱'}
    
    # 檔名不能只包含點和空格
    if re.match(r'^[\.\s]+$', filename):
        return {'valid': False, 'message': '檔名格式不正確'}
    
    return {'valid': True, 'message': '檔名驗證通過'}

def sanitize_filename(filename):
    """清理檔名，移除或替換特殊字符"""
    # 移除或替換不安全的字符
    sanitized = re.sub(r'[<>:"|?*\\/]', '_', filename)
    # 移除前後空白
    sanitized = sanitized.strip()
    # 移除多餘的點
    sanitized = re.sub(r'\.{2,}', '.', sanitized)
    return sanitized

def response(status_code, message, data=None):
    """統一的回應格式"""
    body = {
        'message': message,
        'status': 'success' if 200 <= status_code < 300 else 'error'
    }
    if data:
        body['data'] = data
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'PUT',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(body, ensure_ascii=False)
    }

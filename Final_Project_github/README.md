# 雲端檔案管理系統

這是一個基於 AWS 無伺服器架構的雲端檔案管理系統。它提供使用者註冊、登入、檔案上傳、下載、刪除和重新命名等功能。

## 功能

*   **使用者認證**:
    *   使用者註冊
    *   使用者登入
    *   基於角色的存取控制 (管理員/一般使用者)
*   **檔案管理**:
    *   上傳檔案
    *   列出使用者專屬的檔案
    *   刪除檔案
    *   重新命名檔案

## 系統架構

本專案採用無伺服器架構，主要由以下 AWS 服務組成：

*   **Amazon S3**: 用於託管靜態前端網站，並儲存使用者資料 (JSON 格式) 和上傳的檔案。
*   **AWS Lambda**: 執行後端邏輯，包括使用者認證和檔案操作。
*   **Amazon API Gateway**: 作為前端和後端 Lambda 函數之間的中介，提供 RESTful API 端點。
*   **Amazon CloudWatch**: 用於記錄和監控 Lambda 函數的執行。

### 架構圖

![System Architecture Diagram](architectures/System%20Architecture%20Diagram.png)

## 技術棧

*   **前端**: HTML, CSS, JavaScript
*   **後端**: Python (Boto3)
*   **雲端平台**: AWS (Lambda, S3, API Gateway, CloudWatch)

## API 端點

(以下端點是根據 Lambda 函數推斷的)

*   `POST /register`: 註冊新使用者。
*   `POST /login`: 使用者登入。
*   `POST /files`: 上傳新檔案。
*   `GET /files?username={username}`: 取得指定使用者的檔案列表。
*   `DELETE /files?username={username}&filename={filename}`: 刪除指定的檔案。
*   `PUT /files`: 重新命名檔案。

## 專案結構

```
.
├── architectures/      # 系統架構圖
├── code/
│   ├── backEnd/        # 後端 Lambda 函數
│   │   ├── register_lambda.py
│   │   ├── login_lambda.py
│   │   └── file_manipulate_lambda.py
│   └── frontEnd/       # 前端靜態網頁
│       ├── login.html
│       ├── register.html
│       ├── user.html
│       └── admin.html
└── report/             # 專案報告和文件
```

## 設定與部署

1.  **設定 AWS S3**:
    *   建立一個 S3 儲存貯體 (例如 `awslambda0521`)。
    *   在儲存貯體中建立 `users/`、`users/profiles/` 和 `files/` 資料夾。
    *   將前端檔案 (`code/frontEnd/`) 上傳到 S3 儲存貯體的根目錄，並設定靜態網站託管。

2.  **部署 Lambda 函數**:
    *   為 `register_lambda.py`、`login_lambda.py` 和 `file_manipulate_lambda.py` 分別建立 Lambda 函數。
    *   確保 Lambda 函數具有存取 S3 儲存貯體的 IAM 權限。
    *   在 `file_manipulate_lambda.py` 中，將 `output_bucket` 變數設定為您的 S3 儲存貯體名稱。

3.  **設定 API Gateway**:
    *   建立一個新的 REST API。
    *   為每個 Lambda 函數建立對應的資源和方法 (POST, GET, DELETE, PUT)。
    *   將 API Gateway 的請求與對應的 Lambda 函數整合。
    *   啟用 CORS (跨來源資源共用)。
    *   部署 API。

4.  **更新前端設定**:
    *   在前端 JavaScript 檔案中，將 API Gateway 的 URL 更新為您部署的 API 端點。

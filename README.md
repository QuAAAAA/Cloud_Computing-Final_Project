# Cloud File Management System

This is a cloud file management system based on AWS serverless architecture. It provides features such as user registration, login, file upload, download, deletion, and renaming.

## Features

*   **User Authentication**:
    *   User Registration
    *   User Login
    *   Role-Based Access Control (Admin/User/Guest)
*   **File Management**:
    *   Upload files
    *   Download files
    *   List user-specific files
    *   Delete files
    *   Rename files

## System Architecture

This project uses a serverless architecture, primarily composed of the following AWS services:

*   **Amazon S3**: Used to host the static front-end website and store user data (in JSON format) and uploaded files.
*   **AWS Lambda**: Executes the back-end logic, including user authentication and file operations.
*   **Amazon API Gateway**: Acts as an intermediary between the front-end and back-end Lambda functions, providing RESTful API endpoints.
*   **Amazon CloudWatch**: Used for logging and monitoring the execution of Lambda functions.

### Architecture Diagram

![System Architecture Diagram](architectures/System%20Architecture%20Diagram.png)

## Technology Stack

*   **Front-end**: HTML, CSS, JavaScript
*   **Back-end**: Python (for AWS Lambda)
*   **Cloud Platform**: AWS (Lambda, S3, API Gateway, CloudWatch)

## API Endpoints

*   `POST /register`: Register a new user.
*   `POST /login`: User login.
*   `POST /files`: Upload a new file.
*   `GET /files?username={username}`: Get the file list for a specific user.
*   `DELETE /files?username={username}&filename={filename}`: Delete a specific file.
*   `PUT /files`: Rename a file.

## Project Structure

```
.
├── architectures/      # System architecture diagrams
├── code/
│   ├── backEnd/        # Back-end Lambda functions
│   │   ├── register_lambda.py
│   │   ├── login_lambda.py
│   │   └── file_manipulate_lambda.py
│   └── frontEnd/       # Front-end static pages
│       ├── login.html
│       ├── register.html
│       ├── user.html
│       └── admin.html
└── report/             # Project reports and documents
```

## Setup and Deployment

1.  **Configure AWS S3**:
    *   Create an S3 bucket (e.g., `awslambda0521`).
    *   Create `users/`, `users/profiles/`, and `files/` folders in the bucket.
    *   Upload the front-end files (`code/frontEnd/`) to the root of the S3 bucket and enable static website hosting.

2.  **Deploy Lambda Functions**:
    *   Create separate Lambda functions for `register_lambda.py`, `login_lambda.py`, and `file_manipulate_lambda.py`.
    *   Ensure the Lambda functions have the necessary IAM permissions to access the S3 bucket.
    *   In `file_manipulate_lambda.py`, set the `output_bucket` variable to your S3 bucket name.

3.  **Configure API Gateway**:
    *   Create a new HTTP API.
    *   Create corresponding resources and methods (POST, GET, DELETE, PUT) for each Lambda function.
    *   Integrate the API Gateway requests with the corresponding Lambda functions.
    *   Enable CORS (Cross-Origin Resource Sharing).
    *   Deploy the API.

4.  **Update Front-end Configuration**:
    *   In the front-end JavaScript files, update the API Gateway URL to your deployed API endpoint.

# EDU-PREDICT — Django Backend

Django REST Framework backend for **EDU-PREDICT**, an AI-enabled Student Performance & Academic Management System.

This repository covers **the Python/Django backend side** of the collaborative project. It provides the REST API, authentication and authorization, business logic, academic data management, PostgreSQL integration, Django Admin configuration, validation/error handling, and the API used to expose the Linear Regression performance-prediction model.

## 1. Project Context

EDU-PREDICT manages:

- Users and roles
- Student profiles
- Faculty/staff profiles
- Courses and course categories
- Student enrollments
- Attendance
- Assignments and marks
- Assessments and assessment results
- Aggregated academic performance
- ML prediction records
- Notifications
- Administrative operations

The main academic flow is:

```text
User
  ↓
StudentProfile
  ↓
Enrolment → Course
  ↓
Attendance + Assignments + Assessments
  ↓
Performance
  ↓
ML Prediction
```

The project uses supervised **Linear Regression** to predict a student's expected final academic score. The prediction is an analytical aid and is not a guaranteed final result or a replacement for teacher/academic judgment.

## 2. Django Responsibilities

According to the project requirements, the Python/Django team is responsible for:

- Python and Django backend development
- Django REST Framework APIs
- Authentication and authorization
- Role-based access control
- Django ORM and model design
- Student management
- Course management
- Enrolment management
- Attendance and academic-record management
- Assessment and marks management
- Performance data management
- ML model integration
- Prediction API
- Django Admin configuration
- Validation and error handling

The proposed Django application structure includes:

```text
accounts
courses
students
enrollments
attendance
assignments
assessments
performance
notifications
ml_prediction
```

## 3. Technology Stack

### Backend

- Python
- Django
- Django REST Framework

### Database

- PostgreSQL

### Authentication & Authorization

- Django authentication
- Role-based permissions
- DRF authentication/permission classes

### ML Integration

- Python
- Serialized Linear Regression model
- Prediction endpoint exposed through Django REST Framework

The project specification identifies Linear Regression as the supervised regression algorithm, with `Final_Score` as the target variable.

## 4. Suggested Project Structure

A practical Django structure for this repository is:

```text
django_api_server/
├── manage.py
├── requirements.txt
├── .env
├── .gitignore
├── README.md
│
├── django_api_server/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── accounts/
│   ├── migrations/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── permissions.py
│   ├── serializers.py
│   ├── urls.py
│   ├── views.py
│   └── tests.py
│
├── courses/
│   ├── migrations/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── urls.py
│   ├── views.py
│   └── tests.py
│
├── students/
├── enrollments/
├── attendance/
├── assignments/
├── assessments/
├── performance/
├── notifications/
│
├── ml_prediction/
│   ├── migrations/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── urls.py
│   ├── views.py
│   ├── services.py
│   └── tests.py
│
└── ml_models/
    └── linear_regression_model.*
```

The exact internal structure can be adjusted as implementation progresses, but responsibilities should remain separated by domain.

## 5. Core Domain Models

The project requirements identify these core entities:

| Entity | Purpose |
|---|---|
| `User` | Authentication and account information |
| `StudentProfile` | Student-specific profile data |
| `FacultyProfile` | Faculty/staff information |
| `Course` | Course information |
| `CourseCategory` | Course grouping |
| `Enrolment` | Student-course relationship |
| `Attendance` | Attendance records |
| `Assignment` | Assignment information |
| `Assessment` | Test/exam information |
| `AssessmentResult` | Student assessment scores |
| `Performance` | Aggregated academic indicators |
| `Prediction` | ML prediction records |
| `Notification` | System/user notifications |

### Important Relationships

At a minimum, the model layer should represent:

```text
User
 ├── StudentProfile
 └── FacultyProfile

StudentProfile
 └──< Enrolment >── Course
                       └── CourseCategory

Enrolment
 ├──< Attendance
 ├──< Assignment / assignment results
 └──< AssessmentResult

Student academic records
 └── Performance
       └── Prediction
```

Use Django ORM relationships (`ForeignKey`, `OneToOneField`, `ManyToManyField`) according to the final normalized database design.

## 6. Roles and Permissions

The project defines four primary roles.

| Role | Main permissions |
|---|---|
| Student | Own profile, courses, enrollments, attendance, assignments, results and prediction |
| Faculty/Staff | Assigned students, attendance, marks, performance and prediction viewing |
| Admin | Students, courses, academic records, reports and ML dashboard |
| Super Admin | Users, roles, permissions and complete system configuration |

Permissions should be enforced at the API/backend level rather than relying on frontend route protection.

Recommended implementation:

- Authentication identifies the current user.
- Role/permission classes restrict API access.
- Object-level checks prevent students from accessing another student's private records.
- Faculty access is limited to authorized/assigned academic records.
- Administrative endpoints are restricted to the appropriate staff roles.

## 7. REST API

The PDF specifies the following indicative API endpoints.

### Authentication

```http
POST /api/auth/register/
POST /api/auth/login/
POST /api/auth/logout/
```

### Courses

```http
GET /api/courses/
GET /api/courses/{id}/
```

### Student

```http
GET /api/student/profile/
GET /api/student/courses/
GET /api/student/attendance/
GET /api/student/assignments/
GET /api/student/results/
GET /api/student/performance/
```

### ML Prediction

```http
POST /api/ml/predict/
GET /api/ml/prediction/{student_id}/
```

### Administration

```http
GET /api/admin/dashboard/
GET /api/admin/students/
```

These endpoints are the requirements-level API surface. Additional CRUD endpoints may be introduced where necessary for the backend implementation.

## 8. Prediction API

The backend must expose the trained Linear Regression model through an API.

### Model Definition

```text
Learning type: Supervised Learning
Problem type: Regression
Algorithm: Linear Regression
Target: Final_Score
```

The specification lists these possible input features:

- Attendance Percentage
- Assignment Average
- Mock Test Average
- Practice Hours per Week
- Previous Score
- Modules Completed
- Class Participation

The exact final feature set must be based on actual data availability and correlation with the target.

### Example Request

A prediction request may contain selected numerical academic indicators:

```json
{
  "attendance_percentage": 88,
  "assignment_average": 84,
  "mock_test_average": 78,
  "practice_hours_per_week": 10,
  "previous_score": 80,
  "modules_completed": 90
}
```

### Example Response

```json
{
  "predicted_final_score": 83.7
}
```

`83.7` is only the illustrative value used in the project report. The real API must return the output generated by the trained project model.

### Prediction Flow

```text
Client
  ↓
POST /api/ml/predict/
  ↓
Django validates input
  ↓
Load/use trained Linear Regression model
  ↓
Generate prediction
  ↓
Store prediction record if required
  ↓
Return JSON response
```

The React application consumes this API, but React implementation is not part of this repository.

## 9. ML Model Integration Boundary

The Machine Learning team is responsible for model development and evaluation. The Django backend is responsible for integrating the trained model and exposing it through the prediction API.

The documented ML workflow is:

1. Prepare historical academic data.
2. Load the dataset with Python/pandas.
3. Explore the dataset.
4. Handle missing/inconsistent data.
5. Select useful features.
6. Split training and testing data.
7. Train Linear Regression.
8. Generate test predictions.
9. Evaluate the model.
10. Serialize the trained model.
11. Integrate the model into a Django prediction endpoint.

Recommended regression evaluation metrics from the project requirements:

- MAE
- MSE
- RMSE
- R² Score

The Django repository should not silently retrain the model as part of a normal prediction request unless that behavior is explicitly added as a separate administrative/training workflow.

## 10. PostgreSQL Configuration

PostgreSQL is the required database for the project.

Use environment variables rather than committing database credentials.

Example `.env` values:

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True

DB_NAME=edu_predict_db
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
```

Do not commit a real `.env` file or production credentials.

After configuring the database:

```bash
python manage.py makemigrations
python manage.py migrate
```

Create an administrative account with:

```bash
python manage.py createsuperuser
```

## 11. Local Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd django-backend
```

### 2. Create a virtual environment

macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create `.env` from `.env.example` and configure Django/PostgreSQL settings.

### 5. Apply migrations

```bash
python manage.py migrate
```

### 6. Create a superuser

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

The backend will normally be available at:

```text
http://127.0.0.1:8000/
```

## 12. Django Admin

Django Admin should provide administrative management for the core entities and system operations.

Expected administrative areas include:

- Users
- Students
- Faculty
- Courses
- Categories
- Enrollments
- Attendance
- Assignments
- Assessments
- Assessment results
- Performance
- Predictions
- Notifications

Use `ModelAdmin` configuration to provide useful:

- List displays
- Search
- Filters
- Ordering
- Read-only fields where appropriate
- Role-appropriate administrative controls

## 13. Validation and Error Handling

The backend should validate data before persistence or processing.

Examples include:

- Required fields
- Valid email/account data
- Valid course/enrolment relationships
- Valid attendance values
- Valid academic marks
- Valid assessment results
- Valid prediction feature ranges
- Authorization before accessing student records

REST APIs should return consistent HTTP status codes and JSON error responses.

Example:

```json
{
  "detail": "You do not have permission to access this resource."
}
```

Avoid exposing internal stack traces, database credentials, model internals, or other sensitive implementation details through API responses.

## 14. Testing

The Django side should include tests for:

### Authentication

- Registration
- Login
- Logout
- Invalid credentials
- Unauthorized access

### Authorization

- Student access restrictions
- Faculty/staff permissions
- Admin permissions
- Super-admin operations

### Academic Management

- Course creation/update
- Enrolment
- Attendance
- Assignments
- Assessments
- Results
- Performance aggregation

### Prediction API

- Valid prediction request
- Invalid/missing features
- Unauthorized prediction access
- Model loading/integration
- Prediction response format
- Prediction persistence, if implemented

Run tests with:

```bash
python manage.py test
```

## 15. API Development Guidelines

Keep the backend organized around domain responsibilities.

Recommended separation:

```text
models.py
    Database/domain structure

serializers.py
    Input/output validation and representation

views.py
    HTTP/API behavior

permissions.py
    Access-control rules

services.py
    Reusable business operations where appropriate

urls.py
    API routing

admin.py
    Django Admin configuration
```

Avoid putting large amounts of business logic directly into URL configuration or serializers when a dedicated service/domain layer would make the behavior clearer.

## 16. Security Requirements

At minimum:

- Keep `SECRET_KEY` outside source control.
- Keep database credentials outside source control.
- Do not commit `.env`.
- Do not commit generated model artifacts unless the project explicitly decides to version them.
- Restrict administrative APIs.
- Enforce object-level authorization.
- Validate all client-provided data.
- Use secure production settings when deployed.
- Do not expose debug tracebacks in production.
- Configure allowed hosts appropriately.
- Use HTTPS in production.
- Review CORS/CSRF configuration according to the deployment architecture.

## 17. Backend Scope Boundaries

The Django backend only provides the APIs and backend functionality required for those other project layers to consume.

Other project layers:

- React components
- React Router
- Axios/Fetch frontend integration
- HTML pages
- Tailwind CSS
- Figma designs
- SEO implementation
- Digital marketing activities
- Frontend dashboards
- Frontend course pages

## 18. Integration Architecture

The overall project architecture described in the requirements is:

```text
User / Admin Browser
        ↓
React Frontend
        ↓
Django REST Framework API
        ↓
PostgreSQL Database
        ↓
Machine Learning Model
        ↓
Prediction API
        ↓
React Dashboard
```

For this repository, the implementation boundary is:

```text
              ┌─────────────────────┐
              │   React / Clients   │
              └──────────┬──────────┘
                         │ HTTP/JSON
                         ▼
              ┌─────────────────────┐
              │ Django REST API     │
              │                     │
              │ Auth + Permissions  │
              │ Business Logic      │
              │ Academic APIs       │
              │ Prediction API      │
              └───────┬───────┬─────┘
                      │       │
                      ▼       ▼
              ┌──────────┐  ┌──────────────┐
              │PostgreSQL│  │ Linear       │
              │          │  │ Regression   │
              └──────────┘  │ Model        │
                            └──────────────┘
```

## 19. End-to-End Django Example

Using the project report's example student journey:

1. A student registers through the authentication API.
2. Django creates the user/account data.
3. The student enrols in a course.
4. Django stores the enrolment in PostgreSQL.
5. Attendance, assignment, and assessment records are maintained.
6. Django exposes the student's academic/performance data through protected APIs.
7. The prediction endpoint receives the required features.
8. The integrated Linear Regression model generates the expected final score.
9. The prediction can be stored as a prediction record.
10. Authorized users can retrieve the prediction through the API.

The report's `83.7 / 100` prediction is illustrative only; it must not be hard-coded into the backend.

## 20. Development Checklist

### Project setup

- Django project created
- PostgreSQL connected
- Environment variables configured
- Django REST Framework installed
- `.gitignore` configured

### Accounts

- User model/account strategy finalized
- Registration API
- Login API
- Logout API
- Roles
- Permissions
- Profile management

### Academic management

- Course categories
- Courses
- Student profiles
- Faculty profiles
- Enrollments
- Attendance
- Assignments
- Assessments
- Assessment results
- Performance aggregation
- Notifications

### Administration

- Django Admin configured
- Student management
- Faculty management
- Course management
- Academic record management
- Prediction management
- Appropriate permissions

### ML integration

- Model artifact received from ML workflow
- Feature contract finalized
- Prediction service implemented
- Prediction serializer implemented
- Prediction endpoint implemented
- Prediction records implemented
- Error handling implemented
- Prediction API tested

### API quality

- Validation
- Authentication
- Object-level authorization
- Consistent error responses
- Automated tests
- API documentation

## 21. Important Implementation Notes

The project report intentionally leaves some implementation decisions open. In particular, the exact ML feature set must be finalized after checking data availability and feature/target correlation. Therefore, the backend should avoid hard-coding an ML schema before the ML team's final model contract is agreed.

Likewise, the API list in the report is described as **indicative**. The implementation may add the CRUD/detail endpoints needed to support the specified backend responsibilities while keeping the documented routes compatible with the overall project.

The Django backend should remain focused on its assigned layer so that the collaborative project can integrate cleanly with PostgreSQL, the ML workflow, and the React frontend.

## License

This project is developed as part of a multi-domain collaborative student project.

Copyright (c) 2026 EDU-PREDICT contributors
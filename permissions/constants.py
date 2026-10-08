# permissions/constants.py
# Every permission of the project is written ONCE here, as a constant.
# Views use the constant (a typo then fails immediately), the database stores the same text.
from accounts.models import User

# ---- Users, roles and system settings (Super Admin only)
MANAGE_USERS = "MANAGE_USERS"
MANAGE_PERMISSIONS = "MANAGE_PERMISSIONS"
MANAGE_SYSTEM_SETTINGS = "MANAGE_SYSTEM_SETTINGS"
VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"

# ---- Own account
VIEW_OWN_PROFILE = "VIEW_OWN_PROFILE"
EDIT_OWN_PROFILE = "EDIT_OWN_PROFILE"

# ---- Students and faculty
VIEW_STUDENTS = "VIEW_STUDENTS"
MANAGE_STUDENTS = "MANAGE_STUDENTS"
MANAGE_FACULTY = "MANAGE_FACULTY"

# ---- Courses
ADD_COURSE = "ADD_COURSE"
EDIT_COURSE = "EDIT_COURSE"
DELETE_COURSE = "DELETE_COURSE"
MANAGE_CATEGORIES = "MANAGE_CATEGORIES"

# ---- Enrolments
ENROL_IN_COURSE = "ENROL_IN_COURSE"
VIEW_OWN_ENROLMENTS = "VIEW_OWN_ENROLMENTS"
MANAGE_ENROLMENTS = "MANAGE_ENROLMENTS"

# ---- Attendance
VIEW_OWN_ATTENDANCE = "VIEW_OWN_ATTENDANCE"
VIEW_ATTENDANCE = "VIEW_ATTENDANCE"
MARK_ATTENDANCE = "MARK_ATTENDANCE"

# ---- Assignments
VIEW_OWN_ASSIGNMENTS = "VIEW_OWN_ASSIGNMENTS"
MANAGE_ASSIGNMENTS = "MANAGE_ASSIGNMENTS"
GRADE_ASSIGNMENTS = "GRADE_ASSIGNMENTS"

# ---- Assessments and marks
VIEW_OWN_RESULTS = "VIEW_OWN_RESULTS"
MANAGE_ASSESSMENTS = "MANAGE_ASSESSMENTS"
ENTER_MARKS = "ENTER_MARKS"

# ---- Performance
VIEW_OWN_PERFORMANCE = "VIEW_OWN_PERFORMANCE"
VIEW_PERFORMANCE = "VIEW_PERFORMANCE"

# ---- Machine learning
VIEW_OWN_PREDICTION = "VIEW_OWN_PREDICTION"
VIEW_PREDICTIONS = "VIEW_PREDICTIONS"
RUN_PREDICTION = "RUN_PREDICTION"
MANAGE_ML_MODEL = "MANAGE_ML_MODEL"

# ---- Dashboard, reports, notifications
VIEW_ADMIN_DASHBOARD = "VIEW_ADMIN_DASHBOARD"
VIEW_REPORTS = "VIEW_REPORTS"
EXPORT_REPORTS = "EXPORT_REPORTS"
VIEW_NOTIFICATIONS = "VIEW_NOTIFICATIONS"
SEND_NOTIFICATIONS = "SEND_NOTIFICATIONS"


# Text shown in the React admin panel next to each permission
PERMISSION_DESCRIPTIONS: dict[str, str] = {
    MANAGE_USERS: "Create, edit and deactivate user accounts and change their roles",
    MANAGE_PERMISSIONS: "Change which permissions each role has",
    MANAGE_SYSTEM_SETTINGS: "Change system configuration",
    VIEW_AUDIT_LOGS: "View the audit log",
    VIEW_OWN_PROFILE: "View own profile",
    EDIT_OWN_PROFILE: "Edit own profile",
    VIEW_STUDENTS: "View students (faculty: only assigned students)",
    MANAGE_STUDENTS: "Add, edit and remove students",
    MANAGE_FACULTY: "Add, edit and remove faculty members",
    ADD_COURSE: "Add a course",
    EDIT_COURSE: "Edit a course",
    DELETE_COURSE: "Delete a course",
    MANAGE_CATEGORIES: "Add, edit and delete course categories",
    ENROL_IN_COURSE: "Enrol yourself in a course",
    VIEW_OWN_ENROLMENTS: "View own enrolments",
    MANAGE_ENROLMENTS: "Manage enrolments of all students",
    VIEW_OWN_ATTENDANCE: "View own attendance",
    VIEW_ATTENDANCE: "View attendance of students",
    MARK_ATTENDANCE: "Mark attendance",
    VIEW_OWN_ASSIGNMENTS: "View own assignments and marks",
    MANAGE_ASSIGNMENTS: "Create and edit assignments",
    GRADE_ASSIGNMENTS: "Give marks to assignment submissions",
    VIEW_OWN_RESULTS: "View own assessment results",
    MANAGE_ASSESSMENTS: "Create and edit assessments",
    ENTER_MARKS: "Enter assessment marks",
    VIEW_OWN_PERFORMANCE: "View own performance dashboard",
    VIEW_PERFORMANCE: "View performance of students",
    VIEW_OWN_PREDICTION: "View own predicted final score",
    VIEW_PREDICTIONS: "View predicted final scores of students",
    RUN_PREDICTION: "Generate predictions for any student",
    MANAGE_ML_MODEL: "Train and activate the machine learning model",
    VIEW_ADMIN_DASHBOARD: "View the admin dashboard",
    VIEW_REPORTS: "View reports and analytics",
    EXPORT_REPORTS: "Export reports",
    VIEW_NOTIFICATIONS: "View own notifications",
    SEND_NOTIFICATIONS: "Send notifications to users",
}

_OWN_ACCOUNT = [VIEW_OWN_PROFILE, EDIT_OWN_PROFILE, VIEW_NOTIFICATIONS]

# Which role gets which permissions at the start (from the "Role-Based Access Control" table of the project report).
# The Super Admin can change this later from the React admin panel (or Django admin).
# Run:  python manage.py seed_permissions
ROLE_PERMISSIONS: dict[str, list[str]] = {
    User.Role.STUDENT: _OWN_ACCOUNT + [
        ENROL_IN_COURSE, VIEW_OWN_ENROLMENTS, VIEW_OWN_ATTENDANCE, VIEW_OWN_ASSIGNMENTS,
        VIEW_OWN_RESULTS, VIEW_OWN_PERFORMANCE, VIEW_OWN_PREDICTION,
    ],
    User.Role.FACULTY: _OWN_ACCOUNT + [
        VIEW_STUDENTS, VIEW_ATTENDANCE, MARK_ATTENDANCE, GRADE_ASSIGNMENTS, ENTER_MARKS,
        VIEW_PERFORMANCE, VIEW_PREDICTIONS,
    ],
    User.Role.ADMIN: _OWN_ACCOUNT + [
        VIEW_STUDENTS, MANAGE_STUDENTS, MANAGE_FACULTY,
        ADD_COURSE, EDIT_COURSE, DELETE_COURSE, MANAGE_CATEGORIES, MANAGE_ENROLMENTS,
        VIEW_ATTENDANCE, MARK_ATTENDANCE, MANAGE_ASSIGNMENTS, GRADE_ASSIGNMENTS,
        MANAGE_ASSESSMENTS, ENTER_MARKS, VIEW_PERFORMANCE, VIEW_PREDICTIONS, RUN_PREDICTION,
        MANAGE_ML_MODEL, VIEW_ADMIN_DASHBOARD, VIEW_REPORTS, EXPORT_REPORTS, SEND_NOTIFICATIONS,
    ],
    User.Role.SUPER_ADMIN: list(PERMISSION_DESCRIPTIONS),
}
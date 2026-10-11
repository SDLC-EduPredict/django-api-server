from django.core.management.base import BaseCommand
from django.db import transaction
from courses.models import Course, CourseCategory

CATEGORIES = [
    {"name": "Programming", "slug": "programming", "description": "Learn to code from the basics."},
    {"name": "Web Development", "slug": "web-development", "description": "Build complete websites and web applications."},
    {"name": "Data Science & AI", "slug": "data-science-ai", "description": "Work with data, machine learning and artificial intelligence."},
]

COURSES = [
    {
        "category": "programming", "title": "Python Programming", "slug": "python-programming",
        "short_description": "Python from zero: syntax, data structures, functions, OOP and file handling.",
        "level": Course.Level.BEGINNER, "duration_weeks": 8, "total_modules": 10, "fee": 8000,
        "meta_title": "Python Course in Kolkata | ABC Academy",
        "meta_description": "Join the Python Programming course at ABC Academy, Kolkata. Beginner friendly, hands-on and project based.",
    },
    {
        "category": "web-development", "title": "Django Development", "slug": "django-development",
        "short_description": "Build secure web applications and REST APIs with Django and PostgreSQL.",
        "level": Course.Level.INTERMEDIATE, "duration_weeks": 10, "total_modules": 12, "fee": 12000,
        "meta_title": "Django Course in Kolkata | ABC Academy",
        "meta_description": "Learn Django, Django REST Framework and PostgreSQL at ABC Academy, Kolkata.",
    },
    {
        "category": "web-development", "title": "Full Stack Development", "slug": "full-stack-development",
        "short_description": "React on the front end, Django on the back end, deployed end to end.",
        "level": Course.Level.ADVANCED, "duration_weeks": 24, "total_modules": 20, "fee": 30000,
        "meta_title": "Full Stack Development Course | ABC Academy",
        "meta_description": "Become a full stack developer with React, Django and PostgreSQL at ABC Academy.",
    },
    {
        "category": "data-science-ai", "title": "Data Science", "slug": "data-science",
        "short_description": "Data analysis with pandas, NumPy, visualisation and statistics.",
        "level": Course.Level.INTERMEDIATE, "duration_weeks": 12, "total_modules": 14, "fee": 15000,
        "meta_title": "Data Science Course | ABC Academy",
        "meta_description": "Learn data analysis with Python, pandas and statistics at ABC Academy.",
    },
    {
        "category": "data-science-ai", "title": "Machine Learning", "slug": "machine-learning",
        "short_description": "Supervised and unsupervised learning with scikit-learn, including Linear Regression.",
        "level": Course.Level.ADVANCED, "duration_weeks": 12, "total_modules": 14, "fee": 18000,
        "meta_title": "Machine Learning Course | ABC Academy",
        "meta_description": "Train and evaluate machine learning models with scikit-learn at ABC Academy.",
    },
    {
        "category": "data-science-ai", "title": "Artificial Intelligence", "slug": "artificial-intelligence",
        "short_description": "Neural networks, NLP and practical AI applications.",
        "level": Course.Level.ADVANCED, "duration_weeks": 16, "total_modules": 16, "fee": 22000,
        "meta_title": "Artificial Intelligence Course | ABC Academy",
        "meta_description": "Learn the foundations of AI, neural networks and NLP at ABC Academy.",
    },
]


class Command(BaseCommand):
    help = "Create the ABC Academy sample categories and published courses (safe to run many times)."

    @transaction.atomic
    def handle(self, *args, **options):
        for category in CATEGORIES:
            CourseCategory.objects.get_or_create(slug=category["slug"], defaults=category)

        for course in COURSES:
            values = {**course, "category": CourseCategory.objects.get(slug=course["category"]), "status": Course.Status.PUBLISHED}
            values["description"] = values["short_description"]
            Course.objects.get_or_create(slug=course["slug"], defaults=values)

        self.stdout.write(self.style.SUCCESS(f"{CourseCategory.objects.count()} categories, {Course.objects.count()} courses."))
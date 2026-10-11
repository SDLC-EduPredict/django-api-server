from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify
from accounts.models import User
from core.models import TimeStampedModel


def make_unique_slug(model, text: str) -> str:
    base = slugify(text)[:150] or "item"
    slug = base
    number = 2
    while model.objects.filter(slug=slug).exists():
        slug = f"{base}-{number}"
        number += 1
    return slug


class CourseCategory(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "course categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = make_unique_slug(CourseCategory, self.name)
        super().save(*args, **kwargs)


class Course(TimeStampedModel):
    class Level(models.TextChoices):
        BEGINNER = "BEGINNER", "Beginner"
        INTERMEDIATE = "INTERMEDIATE", "Intermediate"
        ADVANCED = "ADVANCED", "Advanced"

    class Mode(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        OFFLINE = "OFFLINE", "Offline (classroom)"
        HYBRID = "HYBRID", "Hybrid"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    category = models.ForeignKey(CourseCategory, on_delete=models.PROTECT, related_name="courses")
    faculty = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="courses_taught", limit_choices_to={"role": User.Role.FACULTY})
    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    short_description = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=12, choices=Level.choices, default=Level.BEGINNER)
    mode = models.CharField(max_length=7, choices=Mode.choices, default=Mode.OFFLINE)
    duration_weeks = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    total_modules = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    start_date = models.DateField(null=True, blank=True)
    thumbnail = models.ImageField(upload_to="courses/", blank=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT, db_index=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = make_unique_slug(Course, self.title)
        super().save(*args, **kwargs)
from datetime import timedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from nextedge import settings

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    username=models.CharField(unique=True,max_length=128)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    joined = models.DateTimeField(default=timezone.now)
    ADMIN = 'admin'
    CLIENT = 'instructor'
    STUDENT = 'student'

    ROLE_CHOICES = [
        (ADMIN, 'admin'),
        (CLIENT, 'instructor'),
        (STUDENT, 'student'),
    ]
    role = models.CharField(max_length=20, blank=True, null=True, choices=ROLE_CHOICES)
    welcome_email_sent = models.BooleanField(default=False)
    objects = CustomUserManager()
    USERNAME_FIELD = 'email'  
    REQUIRED_FIELDS = []  
    def __str__(self):
        return self.email

class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=100, unique=True)
    expiry = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(length=32)
        if not self.expiry:
            self.expiry = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.expiry > timezone.now()

    def __str__(self):
        return f"Token for {self.user.username} expires at {self.expiry}"
    
class UserProfile(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='login_id')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15)
    bio = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=50)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    active=models.BooleanField(default=True) 
    
class StaffProfile(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='login')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    address=models.CharField(max_length=100)
    city=models.CharField(max_length=50)
    state=models.CharField(max_length=50)
    country_code=models.CharField(max_length=20)
    zip=models.CharField(max_length=10)
    dob = models.DateField()
    phone = models.CharField(max_length=15)
    department = models.CharField(max_length=50, null=True, blank=True) 
    created_at = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)
    
class StaffCourse(models.Model):
    instructor= models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='staff')
    name = models.CharField(max_length=255)
    description = models.TextField()
    payment = models.CharField(max_length=10)
    mode = models.CharField(max_length=20)
    active=models.BooleanField(default=False)
    content = models.FileField(upload_to='topics/', blank=True, null=True)
    lock=models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    approval=models.BooleanField(default=False)
    status =models.CharField(max_length=2)
    type = models.CharField(max_length=100, default='General')
    amount = models.IntegerField(default=0)
    
class Module(models.Model):
    course = models.ForeignKey(StaffCourse, on_delete=models.CASCADE, related_name='course')
    name = models.CharField(max_length=255)

class Topic(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='module')
    name = models.CharField(max_length=255)
    description = models.TextField()
    content = models.FileField(upload_to='topics/', blank=True, null=True)
    
class Quiz(models.Model):
    course = models.ForeignKey(StaffCourse, on_delete=models.CASCADE, related_name='related_course')
    question=models.TextField()
    option1=models.CharField(max_length=150)
    option2=models.CharField(max_length=150)
    option3=models.CharField(max_length=150)
    correct_answer=models.CharField(max_length=10)
    added = models.DateTimeField(default=timezone.now)
    
    
class Enrollment(models.Model):
    student=models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='enrolled_student')
    course = models.ForeignKey(StaffCourse, on_delete=models.CASCADE, related_name='enrolled_course')
    added = models.DateTimeField(default=timezone.now)
    attempts = models.IntegerField(default=0)
    latest_score=models.IntegerField(default=0)
    status=models.BooleanField(default=True)
    
class Department(models.Model):
    department=models.CharField(max_length=150)
    active = models.BooleanField(default=True)
    
class Subdept(models.Model):
    dept=models.ForeignKey(Department, on_delete=models.CASCADE, related_name='staff_department')
    subdept=models.CharField(max_length=150)
    active = models.BooleanField(default=True)
    
class Progress(models.Model):
    student = models.ForeignKey(Enrollment, on_delete=models.CASCADE)
    video = models.ForeignKey(Topic, on_delete=models.CASCADE)
    active=models.BooleanField(default=True)
    watched = models.BooleanField(default=False)
    watched_at = models.DateTimeField(auto_now_add=True)
    
class Certificate(models.Model):
    enrolled = models.ForeignKey(Enrollment, on_delete=models.CASCADE)
    status = models.BooleanField(default=True)  # True if the certificate is awarded
    issued_at = models.DateTimeField(auto_now_add=True) 
    
class Payment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='student_details')
    course = models.ForeignKey(StaffCourse, on_delete=models.CASCADE,related_name='enrolled_courses')
    amount = models.IntegerField()
    status = models.CharField(max_length=20)  # e.g., 'success', 'failed'
    payment_id = models.CharField(max_length=255)  # Store payment ID from Razorpay
    created_at = models.DateTimeField(default=timezone.now)
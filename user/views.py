import csv
from django.core.exceptions import ObjectDoesNotExist
from difflib import SequenceMatcher
import os
from pyexpat.errors import messages
from typing import Counter
import uuid
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import logout
import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from model_mgt import add_new_course, prepare_data, save_model, train_model
from nextedge import settings
from django.contrib.auth.hashers import make_password
from train_model_script import create_user_course_matrix, encode_data, generate_recommendations, load_data, train_svd_model
from user import models
from user.models import Certificate, CustomUser, Department, Enrollment, Module, PasswordResetToken, Payment, Progress, Quiz, StaffProfile, Subdept, Topic, UserProfile,StaffCourse
from django.urls import reverse
from datetime import datetime, timedelta, timezone
from django.utils import timezone
from django.http import HttpResponse
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
import json
from django.db.models import Count
import pandas as pd
from django.core.files.storage import FileSystemStorage

from django.http import JsonResponse

from user.utils.ml_utils import recommend_courses

def login_page(request):
    return render(request, 'user/login_page.html', {'is_register': False})

# def user_profile(request):
#     if request.method == 'POST':
#         user_id=request.user
#         first_name = request.POST.get('first_name')
#         last_name = request.POST.get('last_name')
#         phone_number = request.POST.get('phone_number')
#         bio = request.POST.get('bio')
#         country=request.POST.get('country')
#         profile_picture = request.FILES.get('profile_picture')
        
#         student_instance = user_profile.objects.create(first_name=first_name, last_name=last_name,
#                                                       bio=bio, profile_picture=profile_picture,
#                                                       phone_number=phone_number)
#         return redirect('studentindex')
        
#     return redirect(request,'user_profile.html')

def registerfn(request):
    if request.method == 'POST':
    # Handle registration
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Add validation logic here
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('login_page') 

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email is already taken.")
            return redirect('login_page') 

        user = CustomUser.objects.create_user(username=username, email=email, password=password1, role='student',is_staff=True)
        if user:
            return redirect('login_page')  # Redirect to student index page after successful registration
        else:
            messages.error(request, "Something went wrong. Try again.")
        
def loginfn(request):
    user=request.user
    if user.is_authenticated:
        if UserProfile.objects.filter(user=user).exists():
            return redirect('baseindex')
        else:
            return redirect('user_profile')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            request.session['logged_user'] = user.id 
            if user.is_superuser==True and user.is_staff==True:
                login(request, user)
                return redirect('main_page')
            elif user.role == 'student':
                if UserProfile.objects.filter(user=user).exists():
                    if UserProfile.objects.filter(user=user,active=True).exists():
                        login(request, user)
                        return redirect('baseindex')
                    else:
                       return render(request, 'user/login_page.html', {'deactivated_user': True})
                else:
                    return redirect('user_profile')
            elif user.role == 'instructor':
                if StaffProfile.objects.filter(user=user, active=True).exists():
                    login(request, user)
                    return redirect('landing')
                else:
                    return render(request, 'user/login_page.html', {'deactivated_user': True})
        else:
            messages.error(request, 'Invalid Credentials!Try Again')
            return redirect('login_page')
        
def send_password_reset_email(request, user, token):
    reset_url = request.build_absolute_uri(f'/new_password/{token}/')
    subject = 'Password Reset Request'
    context = {
        'user': user,
        'reset_url': reset_url,
    }
    html_content = render_to_string('user/mail_read.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, 'text/html')
    email.send()

def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get('email')
        associated_users = CustomUser.objects.filter(email=email)
        if associated_users.exists():
            for user in associated_users:
                token = PasswordResetToken.objects.create(user=user)
                send_password_reset_email(request, user, token.token)
            return HttpResponse('A password reset link has been sent to your email.')
        else:
            return HttpResponse('No user is associated with this email address.')
    return render(request, 'user/password_reset.html')

def reset_password(request, token):
    reset_token = PasswordResetToken.objects.filter(token=token, expiry__gt=timezone.now()).first()
    if not reset_token:
        return HttpResponse("Invalid or expired token.")
    
    if request.method == "POST":
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 == password2:
            reset_token.user.set_password(password1)
            reset_token.user.save()
            reset_token.delete()
            return redirect('login_page')
        else:
            return HttpResponse("Passwords do not match.")
    
    return render(request, 'user/new_password.html', {'token': token})

def change_password(request):
    user_profile = UserProfile.objects.get(user=request.user)
    if request.method == "POST":
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 == password2:
            user = request.user
            user.set_password(password1)
            user.save()
            return redirect('login_page')
        else:
            return HttpResponse("Passwords do not match.")
    
    return render(request, 'user/change_password.html', {'user_profile': user_profile})



    
def index(request):
    keyword = request.GET.get('keyword', '')
    courses = StaffCourse.objects.filter(lock=1, active=1, approval=1)

    if keyword:
        courses = courses.filter(name__icontains=keyword)  # Adjust field name as necessary

    context = {'courses': courses}
    return render(request, 'user/index.html', context)

def baseindex(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    student_id = request.user.id 
    # Query for course types and active courses
    course_types = StaffCourse.objects.values('type').annotate(count=Count('type')).distinct()
    courses = StaffCourse.objects.filter(active=True, status='0', lock=True)
    
    # Fetch the user profile
    user_profile = UserProfile.objects.get(user=request.user)
    # Query to find the most enrolled course
    most_enrolled_courses = (
        Enrollment.objects.values('course')
        .annotate(enrollment_count=Count('id'))
        .order_by('-enrollment_count')[:5]
    )

    # Fetch the corresponding course objects
    top_5_courses_objs = []
    for course in most_enrolled_courses:
        course_id = course['course']
        most_enrolled_course_obj = StaffCourse.objects.get(id=course_id)
        top_5_courses_objs.append(most_enrolled_course_obj)
    # # Get recommendations
    # recommended_courses = get_recommended_courses(request.user.id)
    # Render the response
    return render(request, 'user/baseindex.html', {
        'user_profile': user_profile,
        'course_types': course_types,
        'courses': courses,
        'top_5_courses': top_5_courses_objs,
        # 'recommended_courses': recommended_courses,
    })
    # Pass all the context to the template
   
    
def staff_index(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    return render(request,'instructor/instructorindex.html')


def landing(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = StaffProfile.objects.get(user=request.user)
    course_count = StaffCourse.objects.filter(instructor_id=user_profile.id, active=True, lock=True).count()
    enrollment_count = Enrollment.objects.filter(course__instructor=user_profile).count()
    rejected_count = StaffCourse.objects.filter(instructor_id=user_profile.id, status='1').count()
    return render(request,'instructor/landing.html',{'course_count':course_count,'enrollment_count':enrollment_count,'rejected_count':rejected_count})

def password_reset(request):
    return render(request,'user/password_reset.html')

@never_cache
def studentindex(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = UserProfile.objects.get(user=request.user)
    return render(request, 'user/studentindex.html', {'user_profile': user_profile})
    
def adminindex(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    return render(request,'admin/adminindex.html')

def main_page(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    active_profiles_count = UserProfile.objects.filter(active=True).count()
    
    # Count active enrollments in Enrollment
    active_enrollments_count = Enrollment.objects.filter(status=1).count()
    
    # Count courses with lock=1 and active=1 in Course
    active_locked_courses_count = StaffCourse.objects.filter(lock=1, active=1).count()
    attempts_count = Enrollment.objects.filter(attempts=True).count()
    not_enrolled_count = Enrollment.objects.filter(attempts=False).count()

    # Pass these counts to the template
    context = {
        'active_profiles_count': active_profiles_count,
        'active_enrollments_count': active_enrollments_count,
        'active_locked_courses_count': active_locked_courses_count,
        'attempts_count': attempts_count,
        'not_enrolled_count': not_enrolled_count,
    }

    return render(request, 'admin/main_page.html', context)

@never_cache
def user_details(request,user_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profile = get_object_or_404(UserProfile.objects.select_related('user'), user_id=user_id)
    return render(request, 'admin/user_details.html', {'profile': profile})

def new_password(request):
    return render(request,'user/new_password.html')

def user_profile(request):
    return render(request,'user/user_profile.html')


def password_done(request):
    return render(request,'user/password_done.html')

def edit_profile_success(request):
    return render(request,'user/user_profile.html')

def userlogout(request):
    logout(request)  # This logs out the user
    request.session.flush()  # This clears the session, including 'logged_user'
    return redirect('index')

def user_profile(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == 'POST':
        user = request.session['logged_user']
        # Retrieve data from the form
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        bio = request.POST.get('bio')
        country = request.POST.get('country')
        profile_picture = request.FILES.get('profile_picture')

        # Check if the profile exists
        if not UserProfile.objects.filter(user=user).exists():
            # Create a new profile if it does not exist
            profile = UserProfile.objects.create(
                user_id=user, # Directly assign the user object
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                bio=bio,
                country=country,
                profile_picture=profile_picture
            )
            if profile:
                return redirect('baseindex')
        else:
            # Retrieve the existing profile and update fields
            profile = UserProfile.objects.get(user=user)
            profile.first_name = first_name
            profile.last_name = last_name
            profile.phone_number = phone_number
            profile.bio = bio
            profile.country = country
            
            if profile_picture:
                profile.profile_picture = profile_picture
            
            # Save the updated profile
            profile.save()
        return redirect('baseindex')
    return render(request, 'user/user_profile.html')


@never_cache
def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')# Assuming 'index' is the name of your index page URL pattern
    user_profile = UserProfile.objects.get(user=request.user)
    return render(request, 'user/profile_view.html', {'user_profile': user_profile})

@never_cache
def delete_profile_picture(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile =UserProfile.objects.get(user=request.user)
    user_profile.profile_picture.delete()
    user_profile.save()
    return JsonResponse({'status': 'success'})

@never_cache
def replace_profile_picture(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if 'profile_picture' in request.FILES:
        user_profile =UserProfile.objects.get(user=request.user)
        user_profile.profile_picture = request.FILES['profile_picture']
        user_profile.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@never_cache
def edit_profile(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = UserProfile.objects.get(user=request.user)
    
    if request.method == 'POST':
        first_name = request.POST.get('firstName')
        last_name = request.POST.get('lastName')
        phone_number=request.POST.get('phone_number')
        bio = request.POST.get('bio')
        
        user_profile.first_name = first_name
        user_profile.phone_number=phone_number
        user_profile.last_name = last_name
        user_profile.bio = bio
        user_profile.save()
        
        return redirect('profile_view') 
    
    return render(request, 'user/edit_profile.html', {'user_profile': user_profile})

@never_cache
def add_employee(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    dept = Department.objects.filter(active=True)
    return render(request, 'admin/add_employee.html', {'dept': dept})

@never_cache
def staff_registration(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    dept = Department.objects.all()
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')  # You might want to hash passwords in a real application
        first_name = request.POST.get('fname')
        last_name = request.POST.get('lname')
        address = request.POST.get('address')
        city = request.POST.get('Locality')
        state = request.POST.get('State')
        department=request.POST.get('dept')
        country_code = request.POST.get('country_code')
        zip_code = request.POST.get('Zip')
        dob = request.POST.get('dob')
        phone = request.POST.get('phone')

        data = CustomUser.objects.create_user(username=first_name, email=email, password=password, role='instructor',is_superuser=True)
        if data:
            profile = StaffProfile.objects.create(user=data, first_name=first_name, last_name=last_name, address=address, city=city, state=state, country_code=country_code, zip=zip_code, dob=dob, phone=phone,department=department)
            if profile:
                welcome_mail(request, data, password)
                return redirect('adminindex') 
            else:
                return redirect('add_employee') 
        else:
            return redirect('add_employee')
    return render(request, 'admin/add_employee.html',{'dept': dept})
        
@never_cache
def employee_details(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profiles = StaffProfile.objects.select_related('user').filter(active=True)
    return render(request,'admin/employee_details.html',{'profiles': profiles})

def welcome_mail(request, user, password):
    subject = 'Welcome to Next-Edge Team !'
    context = {
        'user': user,
        'password': password,
    }
    html_content = render_to_string('admin/welcome_mail.html', context)
    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.EMAIL_HOST_USER,
        to=[user.email]
    )
    
    email.attach_alternative(html_content, 'text/html')
    email.send()
    
    
def validate_current_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        user = request.user
        user = authenticate(username=user.username, password=current_password)
        if user is not None:
            return JsonResponse({'valid': True})
        else:
            return JsonResponse({'valid': False})

@never_cache
def update_password(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = StaffProfile.objects.get(user=request.user)
    if request.method == "POST":
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 == password2:
            user = request.user
            user.set_password(password1)
            user.save()
            messages.success(request, 'Password updated successfully!')
            return redirect('login_page')
        else:
            messages.error(request, 'Passwords do not match.')
    
    return render(request, 'instructor/update_password.html', {'user_profile': user_profile})

@never_cache
def staff_profile(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = StaffProfile.objects.get(user=request.user)
    return render(request, 'instructor/staff_profile.html', {'profile': user_profile})

def update_staff_profile(request):
    if not request.user.is_authenticated:
        return redirect('index')
    if 'logged_user' not in request.session:
        return redirect('login_page')

    # Get the current user's profile
    user_profile = get_object_or_404(StaffProfile, user=request.user)

    if request.method == 'POST':
        # Extract form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        house_name = request.POST.get('house_name')
        city = request.POST.get('city')
        state = request.POST.get('state')
        zip_code = request.POST.get('zip')

        # Assigning values to the user profile
        user_profile.first_name = first_name
        user_profile.last_name = last_name
        user_profile.phone = phone
        user_profile.address = house_name  # Assuming house_name is stored in address field
        user_profile.city = city
        user_profile.state = state
        user_profile.zip = zip_code

        # Save the updated profile
        user_profile.save()
        return redirect('staff_profile')  # Make sure 'edit_staff_profile' is the correct URL name

    # If GET request, render the edit profile form
    return render(request, 'instructor/edit_staff_profile.html', {'profile': user_profile})
    

@never_cache
def edit_staff_profile(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = StaffProfile.objects.get(user=request.user)
    return render(request,'instructor/edit_staff_profile.html',{'profile': user_profile})

@never_cache
def view_employee_profile(request,user_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profile = get_object_or_404(StaffProfile.objects.select_related('user'), user_id=user_id)
    return render(request, 'admin/view_employee_profile.html', {'profile': profile})

@never_cache
def deactivate_employee(request, user_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profile = get_object_or_404(StaffProfile, user_id=user_id)
    profile.active = False
    profile.save()
    return render(request, 'admin/employee_details.html')

@never_cache
def activate_employee(request, user_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profile = get_object_or_404(StaffProfile, user_id=user_id)
    profile.active = True
    profile.save()
    return render(request, 'admin/employee_details.html')

@never_cache
def deactivated_employee(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profiles = StaffProfile.objects.select_related('user').filter(active=False)
    return render(request,'admin/deactivated_employee.html',{'profiles': profiles})

@never_cache
def active_users(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profiles = UserProfile.objects.select_related('user').filter(active=True)
    return render(request, 'admin/active_users.html', {'profiles': profiles})

@never_cache
def deactivate_user(request, user_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profile = get_object_or_404(UserProfile, user_id=user_id)
    profile.active = False
    profile.save()
    return render(request, 'admin/active_users.html')

@never_cache
def activate_user(request, user_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profile = get_object_or_404(UserProfile, user_id=user_id)
    profile.active = True
    profile.save()
    return render(request, 'admin/active_users.html')

@never_cache
def deactivated_user(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profiles = UserProfile.objects.select_related('user').filter(active=False)
    return render(request,'admin/deactivated_user.html',{'profiles': profiles})

@never_cache
def view_user_profile(request,user_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    profile = get_object_or_404(UserProfile.objects.select_related('user'), user_id=user_id)
    return render(request, 'admin/view_user_profile.html', {'profile': profile})

@never_cache
def view_mycourses(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    
    user_profile = StaffProfile.objects.get(user=request.user)
    department_name = user_profile.department
    department_id = int(department_name)  # Convert to integer if necessary
    department = Department.objects.filter(id=department_id).first()
    course_types = Subdept.objects.filter(active=True,dept_id=department_id)
    return render(request, 'instructor/view_mycourses.html', {'course_types': course_types,'department':department})

@never_cache
def add_course(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = StaffProfile.objects.get(user=request.user)
    department_name = user_profile.department
    department_id = int(department_name)  # Convert to integer if necessary
    department = Department.objects.filter(id=department_id).first()

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        payment = request.POST.get('payment')
        mode = request.POST.get('mode')
        content = request.FILES.get('content')
        course_type = request.POST.get('course_type')
        new_course_type = request.POST.get('new_course_type')
        price=request.POST.get('price')
        
        if course_type == 'Other' and new_course_type:
            course_type=new_course_type
            Subdept.objects.create(subdept=new_course_type, dept=department)
        if payment == 'paid':
            price_value = int(price)
        elif payment == 'free':
            price_value = 0
            
        if name and description and mode and payment:
            user_profile = StaffProfile.objects.get(user=request.user)  # Get the StaffProfile instance
            course = StaffCourse.objects.create(
                name=name,
                description=description,
                payment=payment,
                mode=mode,
                content=content,
                type=course_type,
                instructor=user_profile,status='0',amount=price_value
                # Use the StaffProfile instance
            )
            if course:
                return redirect('my_courses')
    return render(request, 'instructor/add_course.html')

@never_cache
def add_module(request, course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    

    if request.method == 'POST':
        module_name = request.POST.get('name')
        
        if module_name:
            Module.objects.create(name=module_name, course=course)
            return redirect('add_module', course_id=course_id)
    modules = Module.objects.filter(course=course).prefetch_related('module')
    return render(request, 'instructor/add_module.html', {'course': course, 'modules': modules})

@never_cache
def add_topic(request, module_id, course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    module = get_object_or_404(Module, id=module_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        content = request.FILES.get('content')
        
        if name and description and content:
            topic = Topic.objects.create(name=name, description=description, content=content, module_id=module_id)
            return redirect('add_module', course_id=course.id)  # Adjust this line as necessary
    
    return render(request, 'instructor/add_topic.html', {'module': module, 'course': course})


@never_cache
def delete_topic(request,topic_id,course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    modules = Module.objects.filter(course=course).prefetch_related('module')
    topic = get_object_or_404(Topic, id=topic_id)
    topic.delete()
    return render(request, 'instructor/add_module.html', {'course': course, 'modules': modules})

@never_cache
def delete_module(request,module_id,course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    module = get_object_or_404(Module, id=module_id)
    Topic.objects.filter(module=module).delete()
    module.delete()
    modules = Module.objects.filter(course=course)
    return render(request, 'instructor/add_module.html', {'course': course, 'modules': modules})


    

@never_cache
def my_courses(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile =StaffProfile.objects.get(user=request.user)
    courses = StaffCourse.objects.filter(instructor_id=user_profile.id)
    return render(request,'instructor/my_courses.html',{'courses': courses})

@never_cache
def edit_course(request,course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        mode = request.POST.get('mode')
        payment = request.POST.get('payment')
        
        course.name = name
        course.description = description
        course.mode = mode
        course.payment = payment
        
        if 'image' in request.FILES:
            course.image = request.FILES['course-image']
        course.save() 
        
        return redirect('my_courses')  
    return render(request,'instructor/my_courses.html')

@never_cache
def course_approval(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile =StaffProfile.objects.get(user=request.user)
    department_name = user_profile.department
    department_id = int(department_name)  # Convert to integer if necessary
    department = Department.objects.filter(id=department_id).first()
    courses = StaffCourse.objects.filter(instructor_id=user_profile.id,approval=False)
    return render(request,'instructor/course_approval.html',{'courses': courses,'department':department})

@never_cache
def request_course(request,course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    courses = StaffCourse.objects.filter(active=False)
    course.approval = True
    course.save()
    return redirect('course_approval') 


def approval_history(request):
    courses = StaffCourse.objects.filter(approval='1') 
    courses_with_instructors = []

    for course in courses:
        staff_profile = course.instructor  # Fetching the StaffProfile instance
        instructor = staff_profile.user    # Fetching the associated CustomUser instance
        
        courses_with_instructors.append({
            'course': course,
            'instructor': instructor
        })
    return render(request, 'admin/approval_history.html',{'courses_with_instructors': courses_with_instructors})

#list of course that need to be approved
@never_cache
def request_approval_view(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    courses = StaffCourse.objects.filter(active=False, status='0',approval=1)
    courses_with_instructors = []

    for course in courses:
        staff_profile = course.instructor  # Fetching the StaffProfile instance
        instructor = staff_profile.user    # Fetching the associated CustomUser instance
        
        courses_with_instructors.append({
            'course': course,
            'instructor': instructor
        })

    return render(request, 'admin/request_approval.html', {'courses_with_instructors': courses_with_instructors})

#instructor show details of the course
@never_cache
def course_details(request, course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    instructor = course.instructor  # Assuming `instructor` is a ForeignKey in StaffCourse
    modules = Module.objects.filter(course=course)  # Assuming `Module` model has a ForeignKey to `StaffCourse`
    topics = Topic.objects.filter(module__in=modules)  # Assuming `Topic` model has a ForeignKey to `Module`

    context = {
        'course': course,
        'instructor': instructor,
        'modules': modules,
        'topics': topics
    }
    return render(request, 'instructor/course_details.html', context)

def course_details_view_admin(request, course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    instructor = course.instructor  # Assuming `instructor` is a ForeignKey in StaffCourse
    modules = Module.objects.filter(course=course)  # Assuming `Module` model has a ForeignKey to `StaffCourse`
    topics = Topic.objects.filter(module__in=modules)  # Assuming `Topic` model has a ForeignKey to `Module`
    quiz=Quiz.objects.filter(course=course.id)# Assuming `Topic` model has a ForeignKey to `Module`

    context = {
        'course': course,
        'instructor': instructor,
        'modules': modules,
        'topics': topics,
        'quiz':quiz,
    }
    return render(request, 'admin/course_details_view_admin.html', context)


@never_cache
def approve_course(request, course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    course.active = True
    course.lock=True
    course.save()
    courses = StaffCourse.objects.filter(active=False)
    courses_with_instructors = []

    for course in courses:
        staff_profile = course.instructor  # Fetching the StaffProfile instance
        instructor = staff_profile.user    # Fetching the associated CustomUser instance
        
        courses_with_instructors.append({
            'course': course,
            'instructor': instructor
        })
    return redirect('request_approval_view')
    
    return render(request, 'admin/request_approval.html', {'courses_with_instructors': courses_with_instructors})


@never_cache
def reject_course(request, course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    course.status ="1"
    course.save()
    courses = StaffCourse.objects.filter(active=False)
    courses_with_instructors = []

    for course in courses:
        staff_profile = course.instructor  # Fetching the StaffProfile instance
        instructor = staff_profile.user    # Fetching the associated CustomUser instance
        
        courses_with_instructors.append({
            'course': course,
            'instructor': instructor
        })
        return redirect('request_approval_view')

    return render(request, 'admin/request_approval.html', {'courses_with_instructors': courses_with_instructors})

@never_cache
def view_course_details(request, course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    instructor = course.instructor  # Assuming `instructor` is a ForeignKey in StaffCourse
    modules = Module.objects.filter(course=course)  # Assuming `Module` model has a ForeignKey to `StaffCourse`
    topics = Topic.objects.filter(module__in=modules)  # Assuming `Topic` model has a ForeignKey to `Module`
    quiz=Quiz.objects.filter(course=course.id)

    context = {
        'course': course,
        'instructor': instructor,
        'modules': modules,
        'topics': topics,
        'quiz':quiz
    }
    return render(request, 'admin/view_course_details.html', context)

@never_cache
def courses(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = UserProfile.objects.get(user=request.user)
    courses = StaffCourse.objects.filter(active=True, status='0', lock=True)
    modules = Module.objects.filter(course__in=courses) 
    topics = Topic.objects.filter(module__in=modules)  
    context = {
        'courses': courses,  # Changed 'course' to 'courses'
        'modules': modules,
        'topics': topics,
        'user_profile':user_profile
    }
    return render(request, 'user/courses.html', context)

@never_cache
def course_details_view(request,course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = UserProfile.objects.get(user=request.user)
    course = get_object_or_404(StaffCourse, id=course_id)
    student = request.user
    modules = Module.objects.filter(course=course)  # Assuming `Module` model has a ForeignKey to `StaffCourse`
    topics = Topic.objects.filter(module__in=modules)  # Assuming `Topic` model has a ForeignKey to `Module`
    quiz=Quiz.objects.filter(course=course)
    enrollment = Enrollment.objects.filter(student=student.id, course=course, status=True).first()
    
    certificate_instance = None

    # Check if enrollment exists
    if enrollment:
        # Check if a Certificate entry exists for this enrollment
        if Certificate.objects.filter(enrolled_id=enrollment.id).exists():
            # Fetch the certificate instance
            certificate_instance = Certificate.objects.get(enrolled_id=enrollment.id)
    
    total_videos = topics.count()

    # Calculate watched videos based on Progress
    watched_videos = Progress.objects.filter(student=enrollment, video__in=topics, watched=True).count()

    # Calculate progress percentage
    progress = (watched_videos / total_videos * 100) if total_videos > 0 else 0
    
    

        
    context = {
        'course': course,
        'modules': modules,
        'topics': topics,
        'quiz':quiz,
        'enrollment':enrollment,
        'total_videos': total_videos,
        'watched_videos': watched_videos,
        'progress': progress,
        'certificate_instance': certificate_instance,
        'user_profile':user_profile
    }
    return render(request, 'user/course_details_view.html', context)

def course_details_view_staff(request, course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')

    course = get_object_or_404(StaffCourse, id=course_id)

    # Retrieve the instructor's staff profile
    instructor_profile = course.instructor

    # Get the department name or ID as a string
    department_name = instructor_profile.department
    department_id = int(department_name)  # Convert to integer if necessary
    department = Department.objects.filter(id=department_id).first()
    modules = Module.objects.filter(course=course)
    topics = Topic.objects.filter(module__in=modules)
    quiz = Quiz.objects.filter(course=course)

    if department is None or not department.active:
        context = {
            'message': "The Main Course is Unavailable and no action can be performed on this.",
            'course': course,
            'modules': modules,
            'topics': topics,
            'quiz': quiz,
        }
        return render(request, 'instructor/each_course.html', context)

    # Continue with the rest of the logic...


    context = {
        'course': course,
        'modules': modules,
        'topics': topics,
        'quiz': quiz,
        'department': department,
    }

    return render(request, 'instructor/each_course.html', context)



@never_cache
def employee_course(request, instructor_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    instructor = get_object_or_404(StaffProfile, id=instructor_id)
    courses = StaffCourse.objects.filter(instructor=instructor,active=True)
    modules = Module.objects.filter(course__in=courses)
    topics = Topic.objects.filter(module__in=modules)

    # Prepare context data
    course_modules = []
    for course in courses:
        course_data = {
            'course': course,
            'modules': [],
        }
        course_modules_obj = modules.filter(course=course)
        for module in course_modules_obj:
            module_data = {
                'module': module,
                'topics': topics.filter(module=module),
            }
            course_data['modules'].append(module_data)
        course_modules.append(course_data)

    context = {
        'instructor': instructor,
        'course_modules': course_modules,
    }
    return render(request, 'admin/employee_course.html', context)

@never_cache
def add_quiz(request,course_id):
    if not request.user.is_authenticated:
        return redirect('index')
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)

    if request.method == 'POST':
        question = request.POST.get('question')
        option1 = request.POST.get('option1')
        option2 = request.POST.get('option2')
        option3 = request.POST.get('option3')
        correct_answer = request.POST.get('correct_answer')  # Corrected key

        # Create a new Quiz instance
        Quiz.objects.create(
            question=question,
            option1=option1,
            option2=option2,
            option3=option3,
            correct_answer=correct_answer,
            course_id=course.id
        )
    
    # Fetch quiz data
    quiz = Quiz.objects.filter(course_id=course)
    
    return render(request, 'instructor/add_quiz.html', {'quiz': quiz,'course': course})


@never_cache
def edit_question(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        question_text = request.POST.get('question')
        option1 = request.POST.get('option1')
        option2 = request.POST.get('option2')
        option3 = request.POST.get('option3')
        correct_answer = request.POST.get('correct_answer')
        
        try:
            question = get_object_or_404(Quiz, id=question_id)
            question.question = question_text
            question.option1 = option1
            question.option2 = option2
            question.option3 = option3
            question.correct_answer = correct_answer
            question.save()
            response = {'status': 'success', 'message': 'Question updated successfully!'}
        except Exception as e:
            response = {'status': 'error', 'message': str(e)}
        
        return JsonResponse(response)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})
@never_cache 
def delete_quiz(request, course_id, question_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    try:
        course = get_object_or_404(StaffCourse, id=course_id)
        quiz = get_object_or_404(Quiz, id=question_id)
        quiz.delete()
        messages.success(request, 'Quiz deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error occurred: {e}')
    
    return redirect('add_quiz', course_id=course.id)
    
@never_cache
def each_course(request,course_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    return render(request, 'instructor/course_details_view_staff.html', {'course':course})

@never_cache
def upload_excel(request, course_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    success = False
    error_message = None
    
    if request.method == 'POST' and 'excel_data' in request.FILES:
        try:
            excel_file = request.FILES['excel_data']

            fs = FileSystemStorage()
            filename = fs.save(excel_file.name, excel_file)
            file_path = fs.path(filename)

            # Ensure the file has been saved
            if not os.path.exists(file_path):
                error_message = "The uploaded file could not be saved."
                raise ValueError(error_message)

            # Read the Excel file, skipping the first 3 rows
            df = pd.read_excel(file_path, header=3) 

            # Check if required columns are present
            required_columns = ['Question', 'Option1', 'Option2', 'Option3', 'Correct_answer']
            for col in required_columns:
                if col not in df.columns:
                    error_message = f'Missing required column: {col}'
                    raise ValueError(error_message)

            # Process the DataFrame
            for index, row in df.iterrows():
                Quiz.objects.create(
                    question=row['Question'],
                    option1=row['Option1'],
                    option2=row['Option2'],
                    option3=row['Option3'],
                    correct_answer=row['Correct_answer'].lower() if isinstance(row['Correct_answer'], str) else row['Correct_answer'],
                    course_id=course.id
                )
            
            success = True
        except Exception as e:
            error_message = str(e)
    
    quiz = Quiz.objects.filter(course_id=course.id)
    return render(request, 'instructor/add_quiz.html', {
        'quiz': quiz,
        'course': course,
        'success': success,
        'error_message': error_message
    })

@never_cache
def edit_topic(request,topic_id,course_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == 'POST':
        topic_id = request.POST.get('topic_id')
        topic = get_object_or_404(Topic, id=topic_id)
        course = get_object_or_404(StaffCourse, id=course_id)
        modules = Module.objects.filter(course=course).prefetch_related('module')
        topic.name = request.POST.get('name')
        topic.description = request.POST.get('description')
        topic.save()
        messages.success(request, 'Topic updated successfully!')
        return render(request, 'instructor/add_module.html', {'course': course, 'modules': modules})
    
@never_cache   
def enroll_course(request, course_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')

    course = get_object_or_404(StaffCourse, id=course_id)
    student = get_object_or_404(CustomUser, id=request.user.id)

    # Create the enrollment
    enrollment, created = Enrollment.objects.get_or_create(
        course=course,
        student=student,
        defaults={'status': True}
    )
    # Fetch related data for rendering
    modules = Module.objects.filter(course=course)
    topics = Topic.objects.filter(module__in=modules)
    quiz = Quiz.objects.filter(course=course)
    enrollment = Enrollment.objects.filter(student=student.id, course=course, status=True).first()
    user_profile = UserProfile.objects.get(user=request.user)

    context = {
        'course': course,
        'modules': modules,
        'topics': topics,
        'quiz': quiz,
        'enrollment': enrollment,
        'user_profile': user_profile
    }

    # Show success message if enrollment was successful
    if enrollment:
        messages.success(request, 'Congratulations! Course Enrollment Successful')
        return redirect('course_details_view', course_id=course.id)

    return render(request, 'user/course_details_view.html', context)


@never_cache
def course_category(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    departments = Department.objects.filter(active=True)
    subdept = Subdept.objects.filter(active=True)
    deactivated=Department.objects.filter(active=False)
    return render(request,'admin/course_category.html', {'departments': departments,'subdept':subdept,'deactivated':deactivated})

@never_cache
def add_department(request):
    if not request.user.is_authenticated:
        return redirect('index')  # Redirect to index if the user is not authenticated
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == 'POST':
        department_name = request.POST.get('category')
        if department_name:
            Department.objects.create(department=department_name)
            messages.success(request, "Department added successfully!")  # Set success message
            return redirect('course_category')  # Redirect to course_category view after successful addition

    departments = Department.objects.filter(active=True)
    subdept = Subdept.objects.filter(active=True)
    return render(request,'admin/course_category.html', {'departments': departments,'subdept':subdept})

@never_cache
def edit_category(request):
    if not request.user.is_authenticated:
        return redirect('index')  # Redirect to index if the user is not authenticated
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == 'POST':
         category_id = request.POST.get('category_id')
         new_category_name = request.POST.get('category')
    if new_category_name:
            subdep = Department.objects.get(id=category_id)
            subdep.department = new_category_name
            subdep.save()  # Save the updated department name

            # Update the department in all related StaffProfiles
            staff_profiles = StaffProfile.objects.filter(department=subdep)
            for staff_pro in staff_profiles:
                staff_pro.department = subdep  # Assign the updated department object
                staff_pro.save()  # Save each StaffProfile

            messages.success(request, "Category updated successfully!")
            return redirect('course_category')

    departments = Department.objects.filter(active=True)
    subdept = Subdept.objects.filter(active=True)
    return render(request,'admin/course_category.html', {'departments': departments,'subdept':subdept})

@never_cache
def add_subdept(request):
    if not request.user.is_authenticated:
        return redirect('index')  # Redirect to index if the user is not authenticated
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == 'POST':
        subcategory_name = request.POST.get('subcategory')  # Get subcategory name
        department_name = request.POST.get('category')  # Get selected department name

        if subcategory_name and department_name:
                department = Department.objects.get(department=department_name)
                Subdept.objects.create(subdept=subcategory_name, dept=department)
                messages.success(request, "Sub Category added successfully!")
                return redirect('course_category') 
    departments = Department.objects.filter(active=True)
    subdept = Subdept.objects.filter(active=True)
    return render(request,'admin/course_category.html', {'departments': departments,'subdept':subdept})

@never_cache
def remove_category(request, category_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')# Redirect to index if the user is not authenticated
    try:
        # Get the department to be deactivated
        department = Department.objects.get(id=category_id)
        # Deactivate the department
        department.active = False
        department.save()
        # Deactivate related sub-departments
        subdepartments = Subdept.objects.filter(dept=department)
        for subdept in subdepartments:
            subdept.active = False
            subdept.save()
        staff_profiles = StaffProfile.objects.filter(department=department.id)
        if staff_profiles.exists():
            for staff_pro in staff_profiles:
                user_email = staff_pro.user.email  

        message = "Department related subdepartments and staffs deactivated successfully!" 
        messages.success(request, message)
        return redirect('course_category') 
    except Department.DoesNotExist:
        messages.error(request, "Department does not exist.")
    departments = Department.objects.filter(active=True)
    subdept = Subdept.objects.filter(active=True)
    return render(request,'admin/course_category.html', {'departments': departments,'subdept':subdept})


def active_category(request, category_id):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')# Redirect to index if the user is not authenticated
    try:
        # Get the department to be deactivated
        department = Department.objects.get(id=category_id)
        # Deactivate the department
        department.active = True
        department.save()
        # Deactivate related sub-departments
        subdepartments = Subdept.objects.filter(dept=department)
        for subdept in subdepartments:
            subdept.active = True
            subdept.save()
        staff_profiles = StaffProfile.objects.filter(department=department.id)
        if staff_profiles.exists():
            for staff_pro in staff_profiles:
                user_email = staff_pro.user.email  

        message = "Department related subdepartments and staffs Activated successfully!" 
        messages.success(request, message)
        return redirect('course_category') 
    except Department.DoesNotExist:
        messages.error(request, "Department does not exist.")
    departments = Department.objects.filter(active=True)
    subdept = Subdept.objects.filter(active=True)
    return render(request,'admin/course_category.html', {'departments': departments,'subdept':subdept})


@never_cache
def send_dept_remove_mail(request,user):
    subject = 'Course Module Temporarily Unavailable'
    context = {
        'user': user,
    }
    html_content = render_to_string('user/dept_remove.html', context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, settings.EMAIL_HOST_USER, [user.email])
    email.attach_alternative(html_content, 'text/html')
    email.send()

@never_cache
def update_video_progress(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == 'POST':
        video_id = request.POST.get('video_id')
        student_id = request.user.id  # Assuming user is authenticated and has an ID
        
        # Get the enrollment instance
        video = get_object_or_404(Topic, id=video_id)
        
        # Get the associated course_id by traversing relationships
        course_id = video.module.course.id

        # Now you have the course_id, you can use it as needed
        enrollment = get_object_or_404(Enrollment, student_id=student_id, course_id=course_id)
        existing_progress = Progress.objects.filter(student_id=enrollment.id, video_id=video.id).first()
            
        # Create a new Progress entry
        if not existing_progress:
            Progress.objects.create(
            student_id=enrollment.id,
            video_id=video.id,
            watched=True,
            active=True
            )

        # Optionally, redirect after processing
        return JsonResponse({
            'status': 'success',
            'video_url': video.content.url,  # Include the video URL
            'video_name': video.name,  # Include the video name if needed
            
        })

    return JsonResponse({'status': 'failed'}, status=400)

@never_cache
def quiz(request, course_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course = get_object_or_404(StaffCourse, id=course_id)
    quizzes = Quiz.objects.filter(course=course)  # Fetch quizzes for the course
    
    quiz_array = []
    for quiz in quizzes:
        quiz_array.append({
            'question': quiz.question,  # Correct field name
            'option1': quiz.option1,    # Correct field name
            'option2': quiz.option2,    # Correct field name
            'option3': quiz.option3,    # Correct field name
            'correct_answer': quiz.correct_answer  # Correct field name
        })
    
    return render(request, 'user/quiz.html', {
        'course': course,
        'quiz_array': quiz_array  # Pass the quiz array to the template
    })

@never_cache
def update_score(request, course_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == 'POST':
        latest_score = request.POST.get('latest_score')
        
        # Update or create an enrollment record
        enrollment, created = Enrollment.objects.get_or_create(
            student=request.user,
            course_id=course_id,
            defaults={'latest_score': latest_score}
        )
        
        if not created:  # If the enrollment already exists, update the score
            enrollment.latest_score = latest_score
            enrollment.attempts='1'
            enrollment.save()
        latest_score = int(latest_score)
        if latest_score >= 80:
            # Check if a certificate already exists for this enrollment
            certificate_exists = Certificate.objects.filter(enrolled_id=enrollment.id).exists()

            if not certificate_exists:
                # Create a certificate entry if it doesn't already exist
                Certificate.objects.create(
                    enrolled_id=enrollment.id,
                    status=True,  # Assuming `status=True` means the certificate is awarded
                    issued_at=timezone.now()  # Store the current date and time
                )

        return redirect('course_details_view', course_id=course_id)
    return redirect('baseindex')  # Redirect if the request method is not POST

@never_cache
def enrolled_courses_view(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    user_profile = UserProfile.objects.get(user=request.user)
    courses = Enrollment.objects.filter(student=request.user).select_related('course')
    return render(request, 'user/mycourses.html', {'courses': courses,'user_profile':user_profile})

@never_cache
def course_enrollment_details(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    instructor = request.user
    courses = StaffCourse.objects.filter(instructor__user=instructor)

    course_enrollments = []

    for course in courses:
        # Get students enrolled in the course
        enrollments = Enrollment.objects.filter(course=course).select_related('student')
       
        for enrollment in enrollments:
            # Print the values to the console for debugging
            print(f"Email: {enrollment.student.email}, Attempts: {enrollment.attempts}, Latest Score: {enrollment.latest_score}")
            
            course_enrollments.append({
                'student_email': enrollment.student.email,
                'course_name': course.name,
                'attempts': enrollment.attempts,  # Add attempts to context
                'latest_score': enrollment.latest_score,  # Add latest score to context
            })

    context = {
        'course_enrollments': course_enrollments,
    }
    
    return render(request, 'instructor/enrolled_student.html', context)


def recommendation_view(request):
    # Load and prepare the data
    enrollments_df = load_data()
    encoded_df, le_courses, le_students = encode_data(enrollments_df)
    user_course_matrix = create_user_course_matrix(encoded_df)

    # Train the SVD model
    svd_model, user_factors, course_factors = train_svd_model(user_course_matrix)

    # Generate recommendations for a specific student
    student_index = request.user.id  # You can make this dynamic based on user input
    user_vector = user_factors[student_index]
    recommended_courses = generate_recommendations(user_vector, course_factors, le_courses)

    return render(request, 'user/baseindex.html', {'recommended_courses': recommended_courses})

@never_cache
def payment(request, course_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course=get_object_or_404(StaffCourse,id=course_id)
    price = course.amount
    amount = price # Razorpay expects the amount in paise
    return render(request, 'user/payment.html', {'amount': amount, 'course_id': course_id}) 

def check_course_name(request):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    course_name = request.GET.get('name', None).strip()  # Strip leading/trailing spaces
    exact_match = False
    similar_match = False

    # Check for exact match (case-insensitive)
    if StaffCourse.objects.filter(name__iexact=course_name).exists():
        exact_match = True
    else:
        # Check for similar names by comparing word similarity (ignoring case)
        courses = StaffCourse.objects.all()
        for course in courses:
            similarity_ratio = SequenceMatcher(None, course_name.lower(), course.name.lower()).ratio()
            if similarity_ratio > 0.8:  # Threshold for similarity (adjust as needed)
                similar_match = True
                break

    data = {
        'exists_exact': exact_match,
        'exists_similar': similar_match
    }
    return JsonResponse(data)


def check_module_name(request, course_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    if request.method == "GET":
        module_name = request.GET.get('name')
        existing_module = Module.objects.filter(name=module_name, course_id=course_id).exists()
        return JsonResponse({'exists': existing_module})


def check_topic_name(request, course_id):
    if 'logged_user' not in request.session:
        return redirect('login_page')
    topic_name = request.GET.get('name')
    
    # Query to check if the topic name exists in any module of the course
    exists = Topic.objects.filter(module__course_id=course_id, name__iexact=topic_name).exists()
    
    return JsonResponse({'exists': exists})


def save_payment(request):
    if 'logged_user' not in request.session:
        return JsonResponse({"status": "error", "message": "User not logged in."})

    if request.method == "POST":
        payment_id = request.POST.get('payment_id')
        amount = request.POST.get('amount')
        course_id = request.POST.get('course_id')

        if not payment_id or not amount or not course_id:
            return JsonResponse({"status": "error", "message": "Missing payment details."})

        try:
            payment_record = Payment.objects.create(
                user=request.user,
                course_id=course_id,
                amount=amount,
                status='success',  # Assuming payment was successful
                payment_id=payment_id,
                created_at=timezone.now()
            )
            
            return JsonResponse({"status": "success", "message": "Payment saved."})

        except Exception as e:
            return JsonResponse({"status": "error", "message": f"Error saving payment: {str(e)}"})

    return JsonResponse({"status": "error", "message": "Invalid request"})

from django.utils import timezone

def certificate(request, course_id):
    course = get_object_or_404(StaffCourse, id=course_id)
    user = request.user
    student = UserProfile.objects.filter(user_id=user.id).first()
    
    # Find the relevant enrollment
    enrollment = Enrollment.objects.filter(student_id=user.id, course_id=course_id).first()
    
    # Extract date from Certificate model, or use the current date if no certificate exists yet
    certificate_record = Certificate.objects.filter(enrolled_id=enrollment.id).first()
    
    # Use current date if no certificate exists yet or fallback to the stored certificate date
    if certificate_record:
        date = certificate_record.issued_at.strftime('%Y-%m-%d')
    else:
        date = timezone.now().strftime('%Y-%m-%d')
    user_profile = UserProfile.objects.get(user=request.user)

    # Pass the date to the template
    context = {
        'course': course,
        'student': student,
        'date': date,
        'user_profile':user_profile
    }

    return render(request, 'user/certificate.html', context)

def acheivments(request):
    user_id = request.user.id
    # Get the user's profile (optional, in case you need profile data)
    student_profile = UserProfile.objects.filter(user_id=user_id).first()  # Fetch the first profile
    # Get courses the student is enrolled in
    courses = Enrollment.objects.filter(student=request.user.id).select_related('course')

    # Get certificates for the logged-in user
    certificates = Certificate.objects.filter(enrolled__student=request.user)
    user_profile = UserProfile.objects.get(user=request.user)
    return render(request, 'user/acheivments.html', {
        'student_profile': student_profile,
        'courses': courses,
        'certificates': certificates,
        'user_profile':user_profile
    })
    
    
def admin_payment_list(request):
    payments = Payment.objects.select_related('user', 'course').all()
    return render(request, 'admin/payment_list.html', {'payments': payments})

def enrollment_analysis(request):
    # Get total enrollments by course
    enrollment_data = StaffCourse.objects.filter(active=True, lock=True).annotate(total_enrollments=Count('enrolled_course')).values('name', 'total_enrollments')

    # Prepare data for the frontend
    courses = [data['name'] for data in enrollment_data]  # List of course names
    enrollment_counts = [data['total_enrollments'] for data in enrollment_data]  # Total enrollments per course

    # Ensure the data is being sent correctly
    context = {
        'courses': courses,
        'course_enrollments': enrollment_counts,  # Fix the context key to match the template
    }

    return render(request, 'admin/enrollment_analysis.html', context)

def toggle_course_status(request, course_id):
    try:
        course = StaffCourse.objects.get(id=course_id)
        
        # Check if there are any students enrolled in this course
        enrollments = Enrollment.objects.filter(course=course)
        
        if course.active and enrollments.exists():
            # Prevent deactivation if there are students enrolled
            return JsonResponse({
                'success': False,
                'error': 'This course cannot be deactivated because students are enrolled.'
            })
        
        # Toggle the active status
        course.active = not course.active
        course.save()

        # Successful response
        return JsonResponse({
            'success': True,
            'is_active': course.active,
            'message': 'Course has been {} successfully.'.format('activated' if course.active else 'deactivated')
        })
    
    except StaffCourse.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Course not found'
        })
        
        
def course_list(request):
    if not request.user.is_authenticated:
        return redirect('index') 
    if 'logged_user' not in request.session:
        return redirect('login_page')
    courses = StaffCourse.objects.filter(active=True, status='0', lock=True)
    modules = Module.objects.filter(course__in=courses) 
    topics = Topic.objects.filter(module__in=modules)  
    context = {
        'courses': courses,  # Changed 'course' to 'courses'
        'modules': modules,
        'topics': topics,
    }
    return render(request, 'admin/course_list.html', context)


def delete_course(request, course_id):
    course = get_object_or_404(StaffCourse, id=course_id)
    
    # Delete related modules, topics, and quizzes
    modules = Module.objects.filter(course=course)
    topics = Topic.objects.filter(module__in=modules)
    quizzes = Quiz.objects.filter(course=course)

    # Delete related objects in the correct order
    quizzes.delete()  # Delete quizzes related to the course
    topics.delete()   # Delete topics under the course's modules
    modules.delete()  # Delete modules under the course

    # Finally, delete the course itself
    course.delete()
    messages.success(request, 'Course and its related contents have been deleted successfully.')


    # Redirect to 'my_course' page (change to your actual URL name if different)
    return redirect('my_courses')
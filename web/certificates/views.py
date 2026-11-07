from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q

from .models import Certificate, ApprovalLog, UserProfile
from .blockchain import (
    register_onchain,
    approve_onchain,
    revoke_onchain
)
from .excel_helper import generate_sample_excel, process_excel_upload
from .qr_helper import generate_qr_base64

def get_role(user):
    """
    Lấy vai trò của user từ UserProfile.
    Nếu chưa gán profile, fallback về username để tương thích ngược
    với các tài khoản cũ (qlsv, daotao, hieutruong, admin).
    """
    try:
        role = user.profile.role
        if role:
            return role
    except UserProfile.DoesNotExist:
        pass
    return user.username
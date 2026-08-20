"""
Admin sayt uchun kirish/chiqish (login/logout) ko'rinishlari.
Bu Django'ning o'z foydalanuvchi tizimi (auth_user) orqali ishlaydi —
ya'ni superuser yaratish uchun `python manage.py createsuperuser` ishlatiladi.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            error = "Login yoki parol noto'g'ri!"

    return render(request, 'auth/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')

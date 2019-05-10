import re

from django.http import HttpResponse
from django.shortcuts import render, redirect
# Create your views here.
from django.urls import reverse
from django.views import View
from itsdangerous import SignatureExpired
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

from celery_tasks.tasks import send_register_active_email
from dailyfresh import settings
from user.models import User


class RegisterView(View):
    """注册界面的类视图"""

    def get(self, request):
        # 显示注册界面
        return render(request, 'register.html')

    def post(self, request):
        # 注册界面逻辑的处理
        # 接收参数
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 参数验证
        if not all([username, password, email]):
            # 参数不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            # 邮箱格式不正确
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            # 协议不同意
            return render(request, 'register.html', {'errmsg': '请首先同意协议'})

        # 业务处理：用户注册，验证用户是否存在
        try:
            # 用户已经存在
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在可以注册
            user = None

        if user:
            return render(request, 'register.html', {'errmsg': '用户已存在'})

        try:
            user = User.objects.create_user(username, email, password)
            user.is_active = 0
            user.save()
        except Exception as e:
            return render(request, 'register.html', {'errmsg': '用户注册失败，请重试'})

        # 设置激活链接/user/active/user_id
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info).decode('utf8')

        # 发送邮件,delay放到队列中
        send_register_active_email.delay(email, username, token)

        # 返回结果, namespace=goods下面的name=index的视图函数
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """用户激活"""

    def get(self, request, token):
        # token揭密，获取用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']

            # 根据id更改数据库胡is_active
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 跳转登录页面
            return redirect(reverse('user:login'))

        except SignatureExpired as e:
            # 激活链接一过期
            return HttpResponse('激活链接已经过期')


class LoginView(View):
    """登陆界面"""

    def get(self, request):
        return render(request, 'login.html')

import re

from django.contrib.auth import authenticate, login
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

        # 判断是否已经记录了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''

        return render(request, 'login.html', {'username': username, 'checked':checked})


    def post(self, request):
        """使用django内置的认证系统来处理认证和login后的记录登录状态到session"""

        # 接收参数
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remember = request.POST.get('remember')

        # 参数验证
        if not all([username, password]):
            # 参数不完整
            return render(request, 'login.html', {'errmsg': '数据不完整'})


        # 业务处理：用户注册，验证用户是否存在
        # 业务处理:登录校验
        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户名密码正确
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request, user)

                # 获取登录后所要跳转到的地址
                # 默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index'))

                # 跳转到next_url
                response = redirect(next_url) # HttpResponseRedirect

                # 判断是否需要记住用户名

                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')

                # 返回response
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg':'账户未激活'})
        else:
            # 用户名或密码错误
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})

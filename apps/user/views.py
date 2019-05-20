import re

from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, redirect
# Create your views here.
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection
from itsdangerous import SignatureExpired
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer

from celery_tasks.tasks import send_register_active_email
from dailyfresh import settings
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from user.models import User, Address
from utils.Mixin import LoginRequiredMixin


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


class LogoutView(View):
    """退出登录"""

    def get(self, request):

        # 自带logout方法请求session信息
        logout(request)
        # 跳转到首页
        return redirect(reverse('goods:index'))


class UserInfoView(LoginRequiredMixin, View):
    """用户中心-信息页面"""

    def get(self, request):

        # LoginRequiredMixin的自定义扩展类中的login_required装饰器是配合当初的自带login()，登陆后存储session到cache中的
        # 因为自己的user类是继承自自带的认证user类，所以每次请求都会存在一个request.user对象
        # 登陆的话，request.user返回的是一个真实的user对象，否则返回的是一个anonymousUser对象
        # 真实对象的is_authenticated方法返回的是true，匿名对象的这个方法返回的是false
        # django自动会吧request.user对象返回给模板中，不需要手动传递，只需要在模板中调用user即可

        # 数据库查询用户信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取用户的浏览记录
        # from redis import StrictRedis
        # sr = StrictRedis(host='172.16.179.130', port='6379', db=9)等价于下面的自带封装
        con = get_redis_connection('default')

        history_key = 'history_%d' % user.id

        # 获取用户最新浏览的5个商品的id
        sku_ids = con.lrange(history_key, 0, 4)

        # 根据sku_id查询商品的具体信息
        goods_li = [GoodsSKU.objects.filter(id=id) for id in sku_ids]

        # 组织上下文
        context = {
            'page': 'user',
            'address': address,
            'goods_li': goods_li
        }

        return render(request, 'user_center_info.html', context=context)


class UserOrderView(LoginRequiredMixin, View):
    """用户中心-订单页面"""

    def get(self, request, page):

        user = request.user

        # 数据库获取用户的订单信息
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count * order_sku.price
                order_sku.amount = amount

            # 保存单个订单商品的信息
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            order.order_skus = order_skus

        # 进行分页
        paginator = Paginator(orders, 1)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的page对象，废弃因为会加载所有的页码
        order_page = paginator.page(page)

        # 控制限制的页码，只显示最多5个按钮
        # 如果总页数小于5，显示[1-页码]
        # 如果当前页是前三页，显示[1,2,3,4,5]
        # 如果当前页是后三页，显示[4,5,6,7,8] num_pages-4 到num_oages+1
        # 显示当前页，显示当前页的前两页和后两页 [2,3,4,5,6]

        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif num_pages <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages-4, num_pages+1)
        else:
            pages = range(page-2, page+3)

        context = {
            'order_page': order_page,
            'pages': pages,
            'page': 'order',
        }

        return render(request, 'user_center_order.html', context)


class AddressView(LoginRequiredMixin, View):
    """用户中心-地址页面"""

    def get(self, request):

        # 获取登录用户对应User对象
        user = request.user

        # 数据库获取用户的默认和其他地址信息
        address = Address.objects.get_default_address(user)
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})


    def post(self, request):
        """地址的添加"""
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据
        if not all([receiver, addr, phone, type]):
            return render(request, 'user_center_site.html', {'errmsg':'数据不完整'})

        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg':'手机格式不正确'})

        # 业务处理：地址添加
        # 如果用户已存在默认收货地址，添加的地址不作为默认收货地址，否则作为默认收货地址
        # 获取登录用户对应User对象
        user = request.user

        address = Address.objects.get_default_address(user)

        is_default = address == None

        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)

        # 返回应答,get方式刷新地址页面
        return redirect(reverse('user:address'))

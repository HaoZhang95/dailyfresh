from django.http import JsonResponse
from django.shortcuts import render

# Create your views here.
from django.views import View
from django_redis import get_redis_connection

from goods.models import GoodsSKU
from utils.Mixin import LoginRequiredMixin


class CartAddView(View):
    """购物车记录添加"""

    def post(self, request):
        # 接受数据
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})

        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 数据验证
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目格式错误'})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist as e:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 添加购物车记录, redis购物车使用的是hash类型保存的，用到hget获取key中的字典
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        cart_count = conn.hget(cart_key, sku_id)

        if cart_count:
            count += cart_count

        # sku_id存在即更新，不存在则新建
        conn.hset(cart_key, sku_id, count)

        # 验证商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})

        # 获取购物车的数量
        total_count = conn.hlen(cart_key)

        # 返回应答
        return JsonResponse({'res': 5, 'total_count': total_count, 'errmsg': '添加成功'})


class CartInfoView(LoginRequiredMixin, View):
    """购物车页面"""
    def get(self, request):

        # 获取登录的用户
        user = request.user

        # redis获取用户购物车信息
        conn = get_redis_connection('default')
        cart_key = 'cart_%s' % user.id
        cart_dict = conn.hgetall(cart_key)

        skus = []
        total_count = 0
        total_price = 0

        for sku_id, count in cart_dict.items():
            # 根据商品id查询商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的单价
            amount = sku.price * int(count)
            # 动态给sku添加属性
            sku.amount = amount
            sku.count = count
            # 添加到列表
            skus.append(sku)

            total_count += count
            total_price += amount

        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
        }

        render(request, 'cart.html', context)

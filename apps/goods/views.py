from django.core.cache import cache

# Create your views here.
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection

from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from order.models import OrderGoods


class IndexView(View):
    """首页"""

    def get(self, request):
        """
        显示首页，如果访问的是/index的话直接调用视图函数去重新查询一遍
            如果直接访问域名的话，那么加载的是celery服务器中已经渲染好的html代码，不需要数据库重新 查询
            当管理员更新后台的时候，会自动celery重新生成静态html网页，不影响使用
        """
        # 尝试从缓存中获取数据
        context = cache.get('index_page_data')
        if context is None:
            # 获取商品的种类信息
            types = GoodsType.objects.all()

            # 获取轮播图信息
            banners = IndexGoodsBanner.objects.all().order_by('index')

            # 获取促销信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

            # 获取首页分类商品展示信息
            for type in types:
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')

                type.image_banners = image_banners
                type.title_banners = title_banners

            # 上面查询出来的结果都一样，设置缓存
            context = {
                'types': types,
                'goods_banners': banners,
                'promotion_banners': promotion_banners,
            }
            cache.set('index_page_data', context, 3600)

        # 获取首页购物车的数目
        if request.user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%s' % request.user.id
            cart_count = conn.hlen(cart_key)
        else:
            cart_count = 0

        context.update(cart_count=cart_count)

        return render(request, 'index.html', context=context)


class DetailView(View):
    """商品详情界面"""
    def get(self, request, goods_id):

        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist as e:
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = GoodsType.objects.all()
        # 获取商品的评论信息
        sku_order = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]

        # 获取同意spu下面的其他商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取首页购物车的数目
        cart_count = 0
        if request.user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%s' % request.user.id
            cart_count = conn.hlen(cart_key)

            # 向浏览历史中添加
            conn = get_redis_connection('default')
            history_key = 'history_%s' % request.user.id
            # 移除列表中的goods_id如果已经存在, 大于0表示从左移除几个，等于0表示移除所有存在的元素
            conn.lrem(history_key, 0, goods_id)
            # 左侧进行插入
            conn.lpush(history_key, goods_id)
            # 只保存用户最新浏览的5条数据
            conn.ltrim(history_key, 0, 4)

        context = {
            'sku': sku,
            'sku_order': sku_order,
            'types': types,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'same_spu_skus': same_spu_skus,
        }

        return render(request, 'detail.html', context)


class ListView(View):
    """列表页"""
    def get(self, request, type_id, page):

        # 先验证种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist as e:
            return redirect(reverse('goods:index'))

        # 获取下拉的全部种类信息
        types = GoodsType.objects.all()

        # 获取排序的方式
        sort = request.GET.get('sort')
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_id('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_id('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_id('-id')

        # 对skus数据进行分页
        paginator = Paginator(skus, 1)
        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的page对象，废弃因为会加载所有的页码
        skus_page = paginator.page(page)

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

        # 通过page对象获取数据
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取首页购物车的数目
        cart_count = 0
        if request.user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%s' % request.user.id
            cart_count = conn.hlen(cart_key)

        context = {
            "sort": sort,
            "type": type,
            "types": types,
            # "skus_page": skus_page, 会加载所有的页码
            "new_skus": new_skus,
            "cart_count": cart_count,
            "pages": pages,
        }

        return render(request, 'list.html', context)

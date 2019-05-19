import os
from datetime import datetime

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse
from django.views import View
from django_redis import get_redis_connection

from dailyfresh import settings
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from user.models import Address
from utils.Mixin import LoginRequiredMixin
from alipay import AliPay


class CheckPayView(View):
    """因为没有公网，所以下订单后手动去访问去query支付结果么人不是根据return_url"""

    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接受参数
        order_id = request.POST.get('order_id')

        # 判断参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效订单id'})

        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=user,
                pay_method=3,
                order_status=1,
            )
        except OrderInfo.DoesNotExist as e:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 调用支付宝的支付接口
        alipay = AliPay(
            appid="",
            # 默认回调url
            app_notify_url=None,
            app_private_key_string=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            # RSA 或者 RSA2,官网推荐rsa2
            sign_type="RSA2",
            debug=True  # 默认False， true表示访问沙箱的dev接口
        )

        # 手动查询结果
        # 调用支付宝的交易查询接口
        while True:
            response = alipay.api_alipay_trade_query(order_id)

            # response = {
            #         "trade_no": "2017032121001004070200176844", # 支付宝交易号
            #         "code": "10000", # 接口调用是否成功
            #         "invoice_amount": "20.00",
            #         "open_id": "20880072506750308812798160715407",
            #         "fund_bill_list": [
            #             {
            #                 "amount": "20.00",
            #                 "fund_channel": "ALIPAYACCOUNT"
            #             }
            #         ],
            #         "buyer_logon_id": "csq***@sandbox.com",
            #         "send_pay_date": "2017-03-21 13:29:17",
            #         "receipt_amount": "20.00",
            #         "out_trade_no": "out_trade_no15",
            #         "buyer_pay_amount": "20.00",
            #         "buyer_user_id": "2088102169481075",
            #         "msg": "Success",
            #         "point_amount": "0.00",
            #         "trade_status": "TRADE_SUCCESS", # 支付结果
            #         "total_amount": "20.00"
            # }

            code = response.get('code')

            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                # 返回结果
                return JsonResponse({'res': 3, 'message': '支付成功'})
            elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待买家付款
                # 业务处理失败，可能一会就会成功
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                print(code)
                return JsonResponse({'res': 4, 'errmsg': '支付失败'})


class OrderPayView(View):
    """订单支付"""

    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接受参数
        order_id = request.POST.get('order_id')

        # 判断参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效订单id'})

        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=user,
                pay_method=3,
                order_status=1,
            )
        except OrderInfo.DoesNotExist as e:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})

        # 调用支付宝的支付接口
        alipay = AliPay(
            appid="",
            # 默认回调url
            app_notify_url=None,
            app_private_key_string=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            # RSA 或者 RSA2,官网推荐rsa2
            sign_type="RSA2",
            debug=True  # 默认False， true表示访问沙箱的dev接口
        )

        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        total_pay = order.total_price + order.transit_price
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no="20161112",
            total_amount=str(total_pay),
            subject='天天生鲜%s' % order_id,
            return_url="https://example.com",
            notify_url="https://example.com/notify"  # 可选, 不填则使用默认notify url
        )

        # 返回应答,引导html页面跳转去接受支付的界面
        pay_url = 'https://openapi.alipay.com/gateway.do?' + order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})


class OrderPlaceView(LoginRequiredMixin, View):
    """订单提交页面"""

    def post(self, request):

        user = request.user

        # 获取提交的商品ids
        sku_ids = request.POST.getList('sku_ids')

        # 验证sku_ids
        if not sku_ids:
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%s' % user.id
        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            # 获取商品的信息和数量
            sku = GoodsSKU.objects.get(id=sku_id)
            count = conn.hget(cart_key, sku_id)
            amount = sku.price * int(count)

            # 动态添加数量和小计
            sku.count = count
            sku.amount = amount
            skus.append(sku)

            total_price += amount
            total_count += int(count)

        # 写死运费
        transit_price = 10

        # 实付款
        total_pay = total_price + transit_price

        # 获取用户收件地址
        addrs = Address.objects.filter(user=user)
        sku_ids = ''.join(sku_ids)
        # 组织上下文
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'sku_ids': sku_ids,
        }

        return render(request, 'place_order.html', context)


class OrderCommitView(View):
    """订单提交：悲观锁"""

    @transaction.atomic
    def post(self, request):

        # 验证用户
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接受参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 验证参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法支付方式'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist as e:
            return JsonResponse({'res': 3, 'errmsg': '地址不存在'})

        # 创建订单核心业务
        # 创建订单核心业务

        # 组织参数
        # 订单id: 20171122181630+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            # 用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 获取商品的信息
                try:
                    # select * from df_goods_sku where id=sku_id for update;
                    # 在查询的时候就进行加锁，其他进程需要等待该进行commit或者rollback之后才释放锁

                    """
                        悲观锁就是在查询的时候就进行枷锁
                        乐观锁不在查询的时候加锁，而是在判断更新库存的时候和之前查到的库存是不是相等
                        不相等的话说明其间别人把库存进行了修改
                    """
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except:
                    # 商品不存在
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                # 从redis中获取用户所要购买的商品的数量
                count = conn.hget(cart_key, sku_id)

                # 判断商品的库存
                if int(count) > sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                # 向df_order_goods表中添加一条记录
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price)

                # 更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # 累加计算订单商品的总数量和总价格
                amount = sku.price * int(count)
                total_count += int(count)
                total_price += amount

            # 更新订单信息表中的商品的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 提交事务,否则不会提交
        transaction.savepoint_commit(save_id)

        # 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res': 5, 'message': '创建成功'})


"""
    冲突比较少的时候使用乐观锁，3次之内成功，不需要加锁释放锁的时间
    冲突多的情况使用悲观锁，不需要循环，但是需要加锁释放锁的时间
"""


class OrderCommitView1(View):
    """
    订单提交：乐观锁
    需要在mysql的配置文件中添加mysql的事务隔离级别为read-commited只读提交的内容
    防止读取不到另一个事务提交后的更新数据
    """

    @transaction.atomic
    def post(self, request):

        # 验证用户
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接受参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 验证参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法支付方式'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist as e:
            return JsonResponse({'res': 3, 'errmsg': '地址不存在'})

        # 创建订单核心业务
        # 创建订单核心业务

        # 组织参数
        # 订单id: 20171122181630+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                             user=user,
                                             addr=addr,
                                             pay_method=pay_method,
                                             total_count=total_count,
                                             total_price=total_price,
                                             transit_price=transit_price)

            # 用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',')
            for sku_id in sku_ids:
                # 获取商品的信息
                for i in range(3):

                    try:
                        # select * from df_goods_sku where id=sku_id for update;
                        # 在查询的时候就进行加锁，其他进程需要等待该进行commit或者rollback之后才释放锁

                        """
                            悲观锁就是在查询的时候就进行枷锁
                            乐观锁不在查询的时候加锁，而是在判断更新库存的时候和之前查到的库存是不是相等
                            不相等的话说明其间别人把库存进行了修改
                        """
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except:
                        # 商品不存在
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})

                    print('user:%d stock:%d' % (user.id, sku.stock))
                    # 从redis中获取用户所要购买的商品的数量
                    count = conn.hget(cart_key, sku_id)

                    # 判断商品的库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                    # 更新商品的库存和销量
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    # 返回受影响的行数，表示1更新成功，返回0表示更新失败
                    res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock) \
                        .update(stock=new_stock, sales=new_sales)

                    if res == 0:
                        if i == 2:
                            # 尝试到第3次
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败'})
                        else:
                            continue

                    # 向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(order=order,
                                              sku=sku,
                                              count=count,
                                              price=sku.price)

                    # 累加计算订单商品的总数量和总价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount

                    # 若用户不到3此酒秒杀成功直接跳出循环
                    break

            # 更新订单信息表中的商品的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 提交事务,否则不会提交
        transaction.savepoint_commit(save_id)

        # 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res': 5, 'message': '创建成功'})


class CommentView(View):
    """订单评论"""
    def get(self, request, order_id):
        """提供评论页面"""
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 根据订单的状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            # 计算商品的小计
            amount = order_sku.count*order_sku.price
            # 动态给order_sku增加属性amount,保存商品小计
            order_sku.amount = amount
        # 动态给order增加属性order_skus, 保存订单商品信息
        order.order_skus = order_skus

        # 使用模板
        return render(request, "order_comment.html", {"order": order})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user
        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        # 循环获取订单中商品的评论内容
        for i in range(1, total_count + 1):
            # 获取评论的商品的id
            sku_id = request.POST.get("sku_%d" % i) # sku_1 sku_2
            # 获取评论的商品的内容
            content = request.POST.get('content_%d' % i, '') # cotent_1 content_2 content_3
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

        order.order_status = 5 # 已完成
        order.save()

        return redirect(reverse("user:order", kwargs={"page": 1}))

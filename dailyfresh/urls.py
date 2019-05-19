"""dailyfresh URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # 富文本编辑器注册
    re_path('tinymce/', include('tinymce.urls')),
    # 全文检索框架
    re_path('search/', include('haystack.urls')),

    # 注册自定义应用的路由
    re_path('user/', include(('user.urls', 'user'), namespace='user')),
    re_path('cart/', include(('cart.urls', 'cart'), namespace='cart')),
    re_path('order/', include(('order.urls', 'order'), namespace='order')),
    re_path(r'^', include(('goods.urls', 'goods'), namespace='goods')),
]

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
from django.urls import re_path

from order import views

urlpatterns = [
    re_path('^place$', views.OrderPlaceView.as_view(), name='place'),
    re_path('^commit$', views.OrderCommitView.as_view(), name='commit'),
    re_path('^pay$', views.OrderPayView.as_view(), name='pay'),
    re_path('^check$', views.CheckPayView.as_view(), name='check'),
    re_path('^comment/(?P<order_id>.+)$', views.CommentView.as_view(), name='comment'),
]

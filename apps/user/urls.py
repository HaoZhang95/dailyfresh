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
from django.contrib.auth.decorators import login_required
from django.urls import re_path

from user.views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, AddressView, LogoutView

urlpatterns = [

    re_path('^register$', RegisterView.as_view(), name='register'),
    re_path('^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),
    re_path('^login$', LoginView.as_view(), name='login'),
    re_path('^logout$', LogoutView.as_view(), name='logout'),

    re_path('^$',  UserInfoView.as_view(), name='user'),
    re_path('^order$', UserOrderView.as_view(), name='order'),
    re_path('^address$', AddressView.as_view(), name='address'),
]

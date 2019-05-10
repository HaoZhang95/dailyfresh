from celery import Celery


from django.core.mail import send_mail

from dailyfresh import settings

"""
    关于celery的说明:
    1- 代码库-redis中间人-worker 可能并不是都在同一台计算机，但是worker的那一台计算机必须拥有代码库中的代码
    2- 代码库中的代码不需要加上下面的django初始化环境，因为runserver的时候就已经初始化好了，但是worker的那一台计算机必须加上django的环境环境初始化
    3- worker的那一台电脑，并不需要运行代码库，而是需要切换到代码目录下启动celery：celery -A celery_tasks.tasks worker -l info
    4- 代码库中当用户点击注册的时候使用delay()把任务加载到redis中， worker中监听8号库中的redis，有任务就去处理 
    5- 因为本次编写都在同一台电脑，所以加上下面的初始化代码
    6- 初始化django否则处理email的时候话读取不到settings下面的settings.EMAIL_FROM
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
django.setup()


# 创建一个celery对象,并且命名name
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/8')

# 装饰函数使用app
@app.task
def send_register_active_email(to_email, username, token):
    """发送激活邮件"""
    # 发送邮件
    subject = '天天生鲜激活信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    html_message = '<h1>%s, 欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户<br/><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (
        username, token, token)

    try:
        send_mail(subject,
                  message,
                  sender,
                  receiver,
                  html_message=html_message, fail_silently=False)
    except Exception as e:
        print(e)

from django.core.files.storage import Storage
from django.conf import settings
from fdfs_client.client import Fdfs_client


class FDFSStorage(Storage):
    """Fastfds文件存储类"""
    def __init__(self, client_conf=None, base_url=None):

        if client_conf == None:
            client_conf = settings.FDFS_CLIENT_CONF

        if base_url == None:
            base_url = settings.FDFS_URL

        self.client_conf = client_conf
        self.base_url = base_url


    def _open(self, name, mode='rb'):
        '''打开文件时使用会调用的方法，必须重写open和save'''
        pass


    def _save(self, name, content):
        """上传的时候会被调用的方法"""
        # name： test.jpg
        # content: 图片内容的file对象

        # 创建一个fastfds对象
        client = Fdfs_client(self.client_conf)

        # 上传文件到fast dfs系统中
        res = client.upload_by_buffer(content.read())

        # 返回一个dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }
        if res.get('Status') != 'Upload successed.':
            # 上传失败
            raise Exception('上传文件到fast dfs失败')

        # 获取返回的文件ID，注意id并不是文件名，没带jpg的格式
        filename = res.get('Remote file_id')

        return filename

    # 1.jpg
    def exists(self, name):
        '''Django判断文件名是否可用,因为fastfds的文件名不可能重复'''
        return False

    def url(self, name):
        '''返回访问文件的url路径，通过GoodsType.image.url获取goods模型类中image属性的url'''
        return self.base_url + name








from django.contrib import admin

# Register your models here.
from django.core.cache import cache

from goods.models import GoodsType, IndexPromotionBanner, IndexGoodsBanner, IndexTypeGoodsBanner


class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        """
        当促销页被管理员修改时，会触发modelAdmin自动的save_model方法
        在这里需要重新生成index静态文件
        """
        super(BaseModelAdmin, self).save_model(request, obj, form, change)

        # 发出任务让celery重新生成静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html()

        # 更新首页的缓存
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        """管理员删除时候更新index页面"""
        super(BaseModelAdmin, self).delete_model(request, obj)

        # 发出任务让celery重新生成静态页面
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html()

        # 更新首页的缓存
        cache.delete('index_page_data')


class IndexPromotionBannerAdmin(BaseModelAdmin):
    pass


class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass


class GoodsTypeAdmin(BaseModelAdmin):
    pass


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass


admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
admin.site.register(IndexTypeGoodsBanner, IndexTypeGoodsBannerAdmin)
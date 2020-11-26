from django.contrib import admin
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin

from .models import Article, ArticleTag


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass


@admin.register(ArticleTag)
class ArticleTagAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass

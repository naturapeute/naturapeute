"""Admin configuration for the blog application."""

from django.contrib import admin
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin

from .models import Article, ArticleTag


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin, DynamicArrayMixin):
    """Admin configuration for Article model."""
    pass


@admin.register(ArticleTag)
class ArticleTagAdmin(admin.ModelAdmin, DynamicArrayMixin):
    """Admin configuration for ArticleTag model."""
    pass

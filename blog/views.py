from django.http import Http404
from django.views.generic import DetailView, ListView

from core.teable_repository import get_teable_repository, teable_enabled

from .models import Article


class HomeView(ListView):
    model = Article
    template_name = "blog/index.html"
    context_object_name = "articles"

    def get_queryset(self):
        if teable_enabled():
            return get_teable_repository().articles()
        return super().get_queryset()


class ArticleView(DetailView):
    model = Article
    template_name = "blog/article.html"
    context_object_name = "article"

    def get_object(self, queryset=None):
        if teable_enabled():
            article = get_teable_repository().article_by_slug(self.kwargs["slug"])
            if not article:
                raise Http404(f"Article not found with slug {self.kwargs['slug']}")
            return article
        return super().get_object(queryset)

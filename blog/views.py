from django.views.generic import ListView, DetailView

from .models import Article


class HomeView(ListView):
    model = Article
    template_name = "blog/index.html"
    context_object_name = "articles"


class ArticleView(DetailView):
    model = Article
    template_name = "blog/article.html"

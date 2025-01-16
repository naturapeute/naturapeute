"""Views for the blog application."""

from django.views.generic import ListView, DetailView

from .models import Article


class HomeView(ListView):
    """View for displaying the list of articles on the home page."""
    model = Article
    template_name = "blog/index.html"
    context_object_name = "articles"


class ArticleView(DetailView):
    """View for displaying a single article."""
    model = Article
    template_name = "blog/article.html"

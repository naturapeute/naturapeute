"""Models for the blog application."""

from django.db import models
from django.utils.text import slugify
from django.utils.html import strip_tags
from django.template.defaultfilters import truncatewords, wordcount, striptags


class Slugable:
    """Mixin to automatically generate slugs from a specified field."""
    slug_from_field = ""

    def save(self, *args, **kwargs):
        """Generate slug from the specified field if not already set."""
        if not self.slug:
            self.slug = slugify(getattr(self, self.slug_from_field))
        return super().save(*args, **kwargs)


class Article(Slugable, models.Model):
    """Model representing a blog article."""
    def upload_to(self, filename):
        """Generate upload path for article images."""
        return f"article/{filename}"

    slug_from_field = "title"

    tags = models.ManyToManyField("ArticleTag", related_name="articles")
    title = models.CharField(max_length=150)
    image = models.ImageField(
        max_length=200,
        blank=True,
        null=True,
        upload_to=upload_to
    )
    slug = models.SlugField(max_length=150, unique=True)
    body = models.TextField(blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Return string representation of the article."""
        return str(self.title)

    @property
    def summary(self) -> str:
        """Return a truncated summary of the article body."""
        return strip_tags(truncatewords(self.body, 50))

    @property
    def reading_time(self) -> int:
        """Calculate estimated reading time in minutes."""
        return round((wordcount(striptags(self.body)) / 225) + .5)

    @property
    def image_url(self) -> str:
        """Get the URL for the article image."""
        if not self.image:
            return ""
        if not self.image.name:
            return ""
        return self.image.url if not str(self.image).startswith("http") else str(self.image)

    class Meta:
        """Meta options for Article model."""
        ordering = ["-creation_date"]


class ArticleTag(models.Model):
    """Model representing a tag for categorizing articles."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    def save(self, *args, **kwargs):
        """Generate slug from name before saving."""
        self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return string representation of the tag."""
        return str(self.name)

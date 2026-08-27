import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageOps, UnidentifiedImageError

from blog.models import Article
from naturapeute.models import OfficePicture, Therapist


def normalized_stem(value):
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "image"


def jpeg_image(image):
    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


class Command(BaseCommand):
    help = "Give extensionless image files normalized .jpg names and update Django references."

    def add_arguments(self, parser):
        parser.add_argument(
            "--root",
            action="append",
            dest="roots",
            required=True,
            help="Directory to scan; may be supplied multiple times.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report planned changes without writing files or database updates.",
        )

    def handle(self, *args, **options):
        roots = [Path(value).expanduser().resolve() for value in options["roots"]]
        dry_run = options["dry_run"]
        mapping = {}
        basename_mapping = defaultdict(set)
        renamed = 0
        skipped = 0
        collisions = 0

        for root in roots:
            if not root.is_dir():
                raise CommandError(f"Image root does not exist or is not a directory: {root}")
            for source in sorted(path for path in root.rglob("*") if path.is_file() and not path.suffix):
                try:
                    with Image.open(source) as image:
                        image_format = image.format
                        converted = image_format != "JPEG"
                        if converted:
                            output = jpeg_image(image)
                        else:
                            output = None
                except (UnidentifiedImageError, OSError):
                    skipped += 1
                    continue

                relative = source.relative_to(root).as_posix()
                stem = normalized_stem(source.name)
                target = source.with_name(f"{stem}.jpg")
                suffix = 2
                while target.exists() and target != source:
                    collisions += 1
                    target = source.with_name(f"{stem}-{suffix}.jpg")
                    suffix += 1
                new_relative = target.relative_to(root).as_posix()
                mapping[relative] = new_relative
                basename_mapping[source.name.lower()].add(new_relative)

                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if converted:
                        output.save(target, "JPEG", quality=92, optimize=True)
                    else:
                        source.rename(target)
                renamed += 1

        if not dry_run:
            self.update_database(mapping, basename_mapping)

        mode = "would rename" if dry_run else "renamed"
        self.stdout.write(
            f"{mode} {renamed} image files; skipped {skipped} non-images; "
            f"resolved {collisions} filename collisions"
        )

    def update_database(self, mapping, basename_mapping):
        updated = {"therapists": 0, "office_pictures": 0, "articles": 0}

        for therapist in Therapist.mixed.only("pk", "photo").iterator():
            new_value = self.rewrite_reference(therapist.photo.name, mapping, basename_mapping)
            if new_value and new_value != therapist.photo.name:
                Therapist.mixed.filter(pk=therapist.pk).update(photo=new_value)
                updated["therapists"] += 1

        for picture in OfficePicture.objects.only("pk", "file").iterator():
            new_value = self.rewrite_reference(picture.file.name, mapping, basename_mapping)
            if new_value and new_value != picture.file.name:
                OfficePicture.objects.filter(pk=picture.pk).update(file=new_value)
                updated["office_pictures"] += 1

        for article in Article.objects.only("pk", "image").iterator():
            new_value = self.rewrite_reference(article.image.name, mapping, basename_mapping)
            if new_value and new_value != article.image.name:
                Article.objects.filter(pk=article.pk).update(image=new_value)
                updated["articles"] += 1

        self.stdout.write(
            "database references updated: "
            + ", ".join(f"{model}={count}" for model, count in updated.items())
        )

    @staticmethod
    def rewrite_reference(value, mapping, basename_mapping):
        if not value or str(value).startswith(("http://", "https://")):
            return None
        value = str(value)
        candidates = [value, value.lstrip("/")]
        for prefix in ("uploads/", "static/uploads/"):
            if value.startswith(prefix):
                candidates.append(value.removeprefix(prefix))
        candidates.append(Path(value).name)

        for candidate in candidates:
            if candidate in mapping:
                return mapping[candidate]
        basename_matches = basename_mapping.get(Path(value).name.lower(), set())
        if len(basename_matches) == 1:
            return next(iter(basename_matches))
        return None

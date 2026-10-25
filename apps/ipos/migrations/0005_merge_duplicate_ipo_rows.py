from collections import defaultdict
import re
from urllib.parse import urlparse

from django.db import migrations


NAME_SUFFIXES = {"ltd", "limited", "inc", "corp", "corporation", "co", "company", "pvt", "private"}


def normalize_name(name):
    name = re.sub(r"\s+IPO$", "", " ".join(name.split()), flags=re.IGNORECASE)
    words = re.sub(r"[^\w&\s]", " ", name.lower()).split()
    while words and words[-1] in NAME_SUFFIXES:
        words.pop()
    return " ".join(words)


def merge_duplicate_ipos(apps, schema_editor):
    Ipo = apps.get_model("ipos", "Ipo")
    database = schema_editor.connection.alias
    groups = defaultdict(list)

    ipos = list(Ipo.objects.using(database).iterator())
    for ipo in ipos:
        parsed = urlparse(ipo.source_url or "")
        path = parsed.path.rstrip("/")
        if len(path.split("/")) >= 3 and path.rsplit("/", 1)[-1].isdigit():
            groups[("url", parsed.netloc.lower(), path)].append(ipo)
        name = normalize_name(ipo.name)
        if name and ipo.open_date:
            groups[("name", name, ipo.open_date)].append(ipo)

    status_rank = {"upcoming": 0, "open": 1, "closed": 2, "listed": 3}
    excluded = {"id", "name", "created_at"}
    fields = [field.name for field in Ipo._meta.concrete_fields if field.name not in excluded]

    merged_ids = set()
    for duplicates in groups.values():
        duplicates = [ipo for ipo in duplicates if ipo.pk not in merged_ids]
        if len(duplicates) < 2:
            continue
        duplicates.sort(key=lambda ipo: ipo.pk)
        keeper, *others = duplicates
        values = {}

        for field in fields:
            current = getattr(keeper, field)
            candidates = [getattr(ipo, field) for ipo in others]
            if field == "status":
                current = max([current, *candidates], key=lambda value: status_rank.get(value, -1))
            elif field == "updated_at":
                current = max([current, *candidates])
            elif current in (None, "", [], {}) and candidates:
                current = next(
                    (value for value in candidates if value not in (None, "", [], {})), current
                )
            if current != getattr(keeper, field):
                values[field] = current

        other_ids = [ipo.pk for ipo in others]
        Ipo.objects.using(database).filter(pk__in=other_ids).delete()
        merged_ids.update(other_ids)
        if values:
            Ipo.objects.using(database).filter(pk=keeper.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("ipos", "0004_ipo_upstox_data_ipo_upstox_id_ipo_upstox_updated_at"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_ipos, migrations.RunPython.noop),
    ]
